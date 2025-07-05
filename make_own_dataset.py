import os
import random
import uuid
from datetime import datetime, timedelta
import time
from faker import Faker
from neo4j import GraphDatabase

# Initialize Faker for generating realistic data
fake = Faker()

# Neo4j connection details - update these with your actual connection info
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "PASSWORD")

class SocialMediaDataGenerator:
    def __init__(self, uri, username, password):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.fake = Faker()
    
    def close(self):
        self.driver.close()
    
    def clear_database(self):
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("Database cleared.")
    
    def create_constraints(self):
        with self.driver.session() as session:
            # Create constraints to ensure uniqueness based on app.py schema
            try:
                # Constraint on Account.name (not id)
                session.run("""
                CREATE CONSTRAINT account_name_unique IF NOT EXISTS 
                FOR (a:Account) REQUIRE a.name IS UNIQUE
                """)
                
                # Constraint on Post.post_id (not id)
                session.run("""
                CREATE CONSTRAINT post_id_unique IF NOT EXISTS 
                FOR (p:Post) REQUIRE p.post_id IS UNIQUE
                """)
                
                # Create index on Post.timestamp
                session.run("""
                CREATE INDEX post_timestamp_index IF NOT EXISTS 
                FOR (p:Post) ON (p.timestamp)
                """)
                
                print("Created constraints and indexes successfully.")
            except Exception as e:
                # For older Neo4j versions that don't support IF NOT EXISTS:
                try:
                    session.run("CREATE CONSTRAINT ON (a:Account) ASSERT a.name IS UNIQUE")
                    session.run("CREATE CONSTRAINT ON (p:Post) ASSERT p.post_id IS UNIQUE")
                    session.run("CREATE INDEX ON (p:Post) FOR (p.timestamp)")
                    print("Created constraints successfully (legacy syntax).")
                except Exception as e:
                    print(f"Constraints already exist or error: {e}")
    
    def generate_dataset(self, num_users=1000, max_posts_per_user=10, follow_probability=0.05, 
                         like_probability=0.1):
        """
        Generate a social media dataset with specified parameters.
        """
        print(f"Generating dataset with {num_users} users...")
        
        # Create users in batches for better performance
        batch_size = 100
        user_names = []
        
        for i in range(0, num_users, batch_size):
            batch_end = min(i + batch_size, num_users)
            print(f"Creating users {i+1} to {batch_end}...")
            
            with self.driver.session() as session:
                batch_user_names = []
                
                for j in range(i, batch_end):
                    user_name = self.fake.user_name() + str(j)  # Ensure uniqueness
                    batch_user_names.append(user_name)
                
                # Use parameterized query for batch creation
                query = """
                UNWIND $users AS userData
                CREATE (a:Account {name: userData})
                """
                
                # Execute the query
                session.run(query, users=batch_user_names)
                
                user_names.extend(batch_user_names)
        
        print(f"Created {len(user_names)} users.")
        
        # Create posts for each user
        all_posts = []
        print("Creating posts...")
        
        for i, user_name in enumerate(user_names):
            if i % 100 == 0:
                print(f"Creating posts for user {i+1}/{len(user_names)}...")
            
            # Random number of posts for this user
            num_posts = random.randint(0, max_posts_per_user)
            
            if num_posts > 0:
                with self.driver.session() as session:
                    user_posts = []
                    
                    for p in range(num_posts):
                        post_id = str(uuid.uuid4())
                        post_content = self.fake.paragraph(nb_sentences=random.randint(1, 5))
                        # Use datetime object instead of string
                        timestamp = datetime.now() - timedelta(days=random.randint(0, 365))
                        
                        user_posts.append({
                            "post_id": post_id,  # Changed from id to post_id
                            "post_content": post_content,  # Changed from content to post_content
                            "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%S")  # ISO format
                        })
                        all_posts.append(post_id)
                    
                    # Create posts in batch for this user
                    query = """
                    MATCH (a:Account {name: $userName})
                    UNWIND $posts AS post
                    CREATE (p:Post {
                        post_id: post.post_id, 
                        post_content: post.post_content,
                        timestamp: datetime(post.timestamp)
                    })
                    CREATE (a)-[:Posts]->(p)
                    """
                    
                    session.run(query, userName=user_name, posts=user_posts)
        
        print(f"Created {len(all_posts)} posts.")
        
        # Create Follows relationships (note capital F to match app.py schema)
        print("Creating follow relationships...")
        
        # Process follows in larger batches
        follow_batch_size = 1000
        follows_batch = []
        
        for follower_name in user_names:
            potential_follows = [name for name in user_names if name != follower_name]
            # Randomly select users to follow based on probability
            follows = random.sample(
                potential_follows,
                k=min(int(len(potential_follows) * follow_probability) + 1, len(potential_follows))
            )
            
            for followed_name in follows:
                follows_batch.append({
                    "follower": follower_name,
                    "followee": followed_name,
                    "since": (datetime.now() - timedelta(days=random.randint(0, 180))).strftime("%Y-%m-%dT%H:%M:%S")
                })
                
                # When batch is full, process it
                if len(follows_batch) >= follow_batch_size:
                    with self.driver.session() as session:
                        query = """
                        UNWIND $follows AS follow
                        MATCH (follower:Account {name: follow.follower})
                        MATCH (followee:Account {name: follow.followee})
                        MERGE (follower)-[r:Follows]->(followee)
                        ON CREATE SET r.since = datetime(follow.since)
                        """
                        session.run(query, follows=follows_batch)
                        follows_batch = []
        
        # Process remaining follows
        if follows_batch:
            with self.driver.session() as session:
                query = """
                UNWIND $follows AS follow
                MATCH (follower:Account {name: follow.follower})
                MATCH (followee:Account {name: follow.followee})
                MERGE (follower)-[r:Follows]->(followee)
                ON CREATE SET r.since = datetime(follow.since)
                """
                session.run(query, follows=follows_batch)
        
        # Create Likes relationships (note capital L to match app.py schema)
        print("Creating likes...")
        
        for i, user_name in enumerate(user_names):
            if i % 100 == 0:
                print(f"Processing likes for user {i+1}/{len(user_names)}...")
            
            # To avoid memory issues, only select a subset of posts to potentially like
            sample_size = min(1000, len(all_posts))
            sampled_posts = random.sample(all_posts, sample_size)
            
            likes_batch = []
            
            for post_id in sampled_posts:
                # Random chance for likes
                if random.random() < like_probability:
                    likes_batch.append({
                        "user": user_name,
                        "post": post_id,
                        "timestamp": (datetime.now() - timedelta(days=random.randint(0, 60))).strftime("%Y-%m-%dT%H:%M:%S")
                    })
            
            # Process likes
            if likes_batch:
                with self.driver.session() as session:
                    query = """
                    UNWIND $likes AS like
                    MATCH (user:Account {name: like.user})
                    MATCH (post:Post {post_id: like.post})
                    MERGE (user)-[r:Likes]->(post)
                    ON CREATE SET r.timestamp = datetime(like.timestamp)
                    """
                    session.run(query, likes=likes_batch)
        
        print("Dataset generation complete!")
    
    def generate_sample_queries(self):
        """Return some sample Cypher queries to explore the generated data"""
        queries = [
            "// Count total number of users\nMATCH (a:Account) RETURN count(a) as totalUsers",
            
            "// Count total number of posts\nMATCH (p:Post) RETURN count(p) as totalPosts",
            
            "// Find users with the most followers\nMATCH (a:Account)<-[f:Follows]-(follower) \nRETURN a.name as userName, count(f) as followerCount \nORDER BY followerCount DESC LIMIT 10",
            
            "// Find users with the most posts\nMATCH (a:Account)-[p:Posts]->(post) \nRETURN a.name as userName, count(p) as postCount \nORDER BY postCount DESC LIMIT 10",
            
            "// Find posts with the most likes\nMATCH (p:Post)<-[l:Likes]-() \nRETURN p.post_content as content, count(l) as likeCount \nORDER BY likeCount DESC LIMIT 10",
            
            "// Find users who both follow each other (mutual follows)\nMATCH (a1:Account)-[:Follows]->(a2:Account)-[:Follows]->(a1) \nRETURN a1.name as user1, a2.name as user2 \nLIMIT 20",
            
            "// Find the most active users (combination of posting, following, liking)\nMATCH (a:Account) \nOPTIONAL MATCH (a)-[:Posts]->(p) \nOPTIONAL MATCH (a)-[:Follows]->() WITH a, count(DISTINCT p) as posts, count(DISTINCT p) as follows \nOPTIONAL MATCH (a)-[:Likes]->() WITH a, posts, follows, count(DISTINCT p) as likes \nRETURN a.name as userName, posts, follows, likes, (posts + follows + likes) as activityScore \nORDER BY activityScore DESC LIMIT 10",
            
            "// Recommended posts for a user\nMATCH (a:Account {name: 'username'})-[:Follows]->(followed:Account)-[:Likes]->(p:Post) \nWHERE NOT (a)-[:Likes]->(p) \nRETURN p.post_content as recommendedPost, count(DISTINCT followed) as likedByConnections \nORDER BY likedByConnections DESC LIMIT 10",
            
            "// Find similar accounts based on follow patterns\nMATCH (a:Account {name: 'username'})-[:Follows]->(followed:Account) \nMATCH (similar:Account)-[:Follows]->(followed) \nWHERE similar <> a \nRETURN similar.name as similarAccount, count(DISTINCT followed) as commonFollows \nORDER BY commonFollows DESC LIMIT 10"
        ]
        
        return "\n\n".join(queries)

# Main execution
if __name__ == "__main__":
    start_time = time.time()
    
    try:
        # Create generator instance
        generator = SocialMediaDataGenerator(URI, USERNAME, PASSWORD)
        
        # Clear existing data (optional, comment if not needed)
        generator.clear_database()
        
        # Create constraints
        generator.create_constraints()
        
        # Generate dataset
        # You can adjust these parameters as needed
        generator.generate_dataset(
            num_users=1000,             # Total number of users
            max_posts_per_user=10,      # Max posts per user (will be random from 0-10)
            follow_probability=0.05,    # 5% chance a user follows another random user
            like_probability=0.1        # 10% chance a user likes a random post
        )
        
        # Print sample queries
        print("\nSample Cypher Queries to explore the data:")
        print(generator.generate_sample_queries())
        
        # Close connection
        generator.close()
        
        elapsed_time = time.time() - start_time
        print(f"\nTotal execution time: {elapsed_time:.2f} seconds")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()