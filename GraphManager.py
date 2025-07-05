import os
from typing import Dict, Any, List, Optional, Union
from neo4j import GraphDatabase
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()  # Load environment variables from .env file

class Neo4jGraphManager:
    """Manager class for Neo4j graph database operations."""
    
    def __init__(
        self, 
        uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        username: str = os.getenv("NEO4J_USERNAME", "neo4j"),
        password: str = os.getenv("NEO4J_PASSWORD", "password")
    ):
        """Initialize with Neo4j connection details."""
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self._ensure_constraints()
        self._ensure_indexes()
    
    def _ensure_constraints(self):
        """Ensure necessary constraints exist in the database."""
        with self.driver.session() as session:
            # Create constraint on Account.name if it doesn't exist
            session.run("""
            CREATE CONSTRAINT account_name_unique IF NOT EXISTS
            FOR (a:Account) REQUIRE a.name IS UNIQUE
            """)
            
            # Create constraint on Post.post_id if it doesn't exist
            session.run("""
            CREATE CONSTRAINT post_id_unique IF NOT EXISTS
            FOR (p:Post) REQUIRE p.post_id IS UNIQUE
            """)
    
    def _ensure_indexes(self):
        """Ensure necessary indexes exist in the database."""
        with self.driver.session() as session:
            # Create index on Post.timestamp if it doesn't exist
            session.run("""
            CREATE INDEX post_timestamp_index IF NOT EXISTS FOR (p:Post) ON (p.timestamp)
            """)
    
    def close(self):
        """Close the Neo4j connection."""
        self.driver.close()
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results."""
        if params is None:
            params = {}
        
        with self.driver.session() as session:
            result = session.run(query, params)
            return [record.data() for record in result]
    
    # Basic Graph Queries
    
    def get_all_nodes(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve all nodes in the graph with pagination."""
        query = """
        MATCH (n)
        RETURN n, labels(n) AS node_type
        LIMIT $limit
        """
        return self.execute_query(query, {"limit": limit})
    
    def get_shortest_path(self, from_name: str, to_name: str) -> List[Dict[str, Any]]:
        """Find shortest path between two accounts."""
        query = """
        MATCH (start:Account {name: $from_name}), (end:Account {name: $to_name}),
        path = shortestPath((start)-[*]-(end))
        RETURN path, length(path) AS path_length
        """
        return self.execute_query(query, {"from_name": from_name, "to_name": to_name})
    
    def get_account_connections(self, name: str, depth: int = 2, limit: int = 100) -> List[Dict[str, Any]]:
        """Get connections (follows) of an account up to specified depth."""
        # Convert depth to string for concatenation
        depth_range = f"1..{depth}"
        query = f"""
        MATCH path = (a:Account {{name: $name}})-[:Follows*{depth_range}]-(connected:Account)
        WHERE a <> connected
        RETURN connected.name AS connection, length(path) AS distance
        ORDER BY distance ASC
        LIMIT $limit
        """
        return self.execute_query(query, {"name": name, "limit": limit})
    
    # Account Management
    
    def add_account(self, name: str, properties: Dict[str, Any] = None) -> Dict[str, Any]:
        """Add a new account to the database."""
        if properties is None:
            properties = {}
        
        # Add name to properties
        all_props = {"name": name}
        all_props.update(properties)
        
        query = """
        CREATE (a:Account $properties)
        RETURN a
        """
        result = self.execute_query(query, {"properties": all_props})
        return result[0] if result else {}
    
    def follow_account(self, follower_name: str, followee_name: str) -> Dict[str, Any]:
        """Create a Follows relationship between accounts."""
        query = """
        MATCH (follower:Account {name: $follower_name})
        MATCH (followee:Account {name: $followee_name})
        WHERE follower <> followee
        MERGE (follower)-[r:Follows]->(followee)
        ON CREATE SET r.since = datetime()
        RETURN follower, followee, r
        """
        result = self.execute_query(query, {
            "follower_name": follower_name,
            "followee_name": followee_name
        })
        return result[0] if result else {}
    
    def unfollow_account(self, follower_name: str, followee_name: str) -> Dict[str, bool]:
        """Remove a Follows relationship between accounts."""
        query = """
        MATCH (follower:Account {name: $follower_name})-[r:Follows]->(followee:Account {name: $followee_name})
        DELETE r
        RETURN count(r) > 0 AS relationship_deleted
        """
        result = self.execute_query(query, {
            "follower_name": follower_name,
            "followee_name": followee_name
        })
        return result[0] if result else {"relationship_deleted": False}
    
    # Post Management
    
    def add_post(self, account_name: str, post_content: str, post_id: str = None) -> Dict[str, Any]:
        """Add a new post for an account."""
        if post_id is None:
            post_id = str(uuid.uuid4())
        
        query = """
        MATCH (a:Account {name: $account_name})
        CREATE (p:Post {
            post_id: $post_id,
            post_content: $post_content,
            timestamp: datetime()
        })
        CREATE (a)-[r:Posts]->(p)
        RETURN a, p, r
        """
        result = self.execute_query(query, {
            "account_name": account_name,
            "post_id": post_id,
            "post_content": post_content
        })
        return result[0] if result else {}
    
    def like_post(self, account_name: str, post_id: str) -> Dict[str, Any]:
        """Create a Likes relationship between an account and a post."""
        query = """
        MATCH (a:Account {name: $account_name})
        MATCH (p:Post {post_id: $post_id})
        MERGE (a)-[r:Likes]->(p)
        ON CREATE SET r.timestamp = datetime()
        RETURN a, p, r
        """
        result = self.execute_query(query, {
            "account_name": account_name,
            "post_id": post_id
        })
        return result[0] if result else {}
    
    def unlike_post(self, account_name: str, post_id: str) -> Dict[str, bool]:
        """Remove a Likes relationship between an account and a post."""
        query = """
        MATCH (a:Account {name: $account_name})-[r:Likes]->(p:Post {post_id: $post_id})
        DELETE r
        RETURN count(r) > 0 AS relationship_deleted
        """
        result = self.execute_query(query, {
            "account_name": account_name,
            "post_id": post_id
        })
        return result[0] if result else {"relationship_deleted": False}
    
    def get_account_posts(self, account_name: str, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        """Get all posts by an account with pagination."""
        query = """
        MATCH (a:Account {name: $account_name})-[:Posts]->(p:Post)
        RETURN p
        ORDER BY p.timestamp DESC
        SKIP $skip
        LIMIT $limit
        """
        return self.execute_query(query, {
            "account_name": account_name,
            "skip": skip,
            "limit": limit
        })
    
    # Advanced Queries
    def find_similar_accounts(self, account_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find similar accounts based on follow patterns and likes."""
        query = """
        // Find accounts that follow the same accounts
        MATCH (a:Account {name: $account_name})-[:Follows]->(followed:Account)
        WITH a, collect(followed) as user_follows
        
        // Find other accounts and their follows, excluding the original account
        MATCH (other:Account)-[:Follows]->(their_followed:Account)
        WHERE other <> a
        
        // Calculate similarity based on common follows
        WITH other, 
             user_follows,
             collect(their_followed) as other_follows,
             size(user_follows) as user_follow_count
        
        WITH other,
             size([x IN other_follows WHERE x IN user_follows]) as common_follows,
             user_follow_count
        
        // Calculate similarity score
        WITH other.name AS similar_account,
             common_follows,
             toFloat(common_follows) / user_follow_count AS similarity_score
        
        // Only return accounts with some similarity
        WHERE similarity_score > 0
        
        RETURN similar_account,
               common_follows,
               similarity_score
        ORDER BY similarity_score DESC, common_follows DESC
        LIMIT $limit
        """
        return self.execute_query(query, {
            "account_name": account_name,
            "limit": limit
        })
    
    def recommend_posts(self, account_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Recommend posts based on account's follows and likes."""
        query = """
        // Find posts liked by accounts that the user follows
        MATCH (a:Account {name: $account_name})-[:Follows]->(followed:Account)-[:Likes]->(p:Post)
        WHERE NOT (a)-[:Likes]->(p) // Exclude posts already liked by the user
        
        WITH p, count(DISTINCT followed) AS followed_likes
        
        // Find posts from accounts that the user follows
        OPTIONAL MATCH (a:Account {name: $account_name})-[:Follows]->(poster:Account)-[:Posts]->(p2:Post)
        WHERE p = p2
        
        WITH p, followed_likes, count(p2) > 0 AS from_followed
        
        // Calculate a recommendation score
        WITH p, followed_likes, from_followed,
             CASE WHEN from_followed THEN 1.5 ELSE 1 END * followed_likes AS recommendation_score
        
        RETURN p.post_id AS post_id,
               p.post_content AS content,
               recommendation_score
        ORDER BY recommendation_score DESC
        LIMIT $limit
        """
        return self.execute_query(query, {
            "account_name": account_name,
            "limit": limit
        })
    
    # PageRank Implementation
    def calculate_pagerank(self, iterations: int = 20, damping: float = 0.85) -> List[Dict[str, Any]]:
        """Calculate PageRank on the social network to find influential accounts."""
        # Implementation using Neo4j's built-in graph algorithms
        query = """
        CALL gds.graph.project(
          'socialGraph',
          'Account',
          {
            FOLLOWS: {
              type: 'Follows',
              orientation: 'NATURAL'
            }
          }
        )
        YIELD graphName
        
        CALL gds.pageRank.stream('socialGraph', {
          maxIterations: $iterations,
          dampingFactor: $damping
        })
        YIELD nodeId, score
        
        MATCH (a:Account) WHERE id(a) = nodeId
        
        RETURN a.name AS account, score AS pagerank
        ORDER BY pagerank DESC
        """
        
        try:
            return self.execute_query(query, {
                "iterations": iterations,
                "damping": damping
            })
        except Exception as e:
            # Fallback if GDS library is not available
            logger.warning(f"PageRank calculation using GDS library failed: {str(e)}")
            logger.info("Using custom PageRank implementation")
            return self._custom_pagerank_implementation(iterations, damping)
            
    def _custom_pagerank_implementation(self, iterations: int = 20, damping: float = 0.85) -> List[Dict[str, Any]]:
        """Custom PageRank implementation if GDS library is not available."""
        # Initialize PageRank
        init_query = """
        MATCH (a:Account)
        SET a.pagerank = 1.0,
            a.prevPagerank = 0.0
        WITH count(a) AS nodes
        RETURN nodes
        """
        result = self.execute_query(init_query)
        total_nodes = result[0]["nodes"] if result else 0
        
        if total_nodes == 0:
            return []
        
        # Perform iterations
        for i in range(iterations):
            # Store previous PageRank
            update_prev_query = """
            MATCH (a:Account)
            SET a.prevPagerank = a.pagerank
            """
            self.execute_query(update_prev_query)
            
            # Calculate new PageRank
            iteration_query = f"""
            MATCH (a:Account)
            OPTIONAL MATCH (a)<-[:Follows]-(follower:Account)
            WITH a, 
                COLLECT(follower) AS followers,
                {1 - damping} AS base_score
                
            UNWIND followers AS f
            OPTIONAL MATCH (f)-[:Follows]->(outlinks)
            WITH a, f, base_score, COUNT(outlinks) AS outlinks_count
            
            WITH a, base_score, SUM(
                CASE 
                    WHEN outlinks_count > 0 THEN f.prevPagerank / outlinks_count
                    ELSE 0
                END
            ) AS incoming_score
            
            SET a.pagerank = base_score + {damping} * incoming_score
            """
            self.execute_query(iteration_query)
        
        # Retrieve results
        result_query = """
        MATCH (a:Account)
        RETURN a.name AS account, a.pagerank AS pagerank
        ORDER BY pagerank DESC
        """
        results = self.execute_query(result_query)
        
        # Clean up properties
        cleanup_query = """
        MATCH (a:Account)
        REMOVE a.pagerank, a.prevPagerank
        """
        self.execute_query(cleanup_query)
        
        return results


    def get_graph_statistics(self) -> Dict[str, Any]:
        """Get basic graph statistics."""
        query = """
        MATCH (n:Account)
        WITH count(n) as nodes
        MATCH ()-[r:Follows]->()
        RETURN nodes as node_count, count(r) as relationship_count
        """
        return self.execute_query(query)

    def get_connected_accounts(self, account_name: str) -> List[Dict[str, Any]]:
        """Get all accounts connected to a specific account."""
        query = """
        MATCH (n:Account {name: $account_name})-[:Follows]->(m:Account)
        RETURN m.name AS connected_account
        """
        return self.execute_query(query, {"account_name": account_name})

    def get_common_connections(self, account1: str, account2: str) -> List[Dict[str, Any]]:
        """Get common connections between two accounts."""
        query = """
        MATCH (a:Account {name: $account1})-[:Follows]->(m:Account)<-[:Follows]-(b:Account {name: $account2})
        RETURN m.name AS common_connection
        """
        return self.execute_query(query, {"account1": account1, "account2": account2})
