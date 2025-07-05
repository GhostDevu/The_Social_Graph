import os
import json
from dotenv import load_dotenv
from NL_Query_Processor import Neo4jLLMQueryProcessor

load_dotenv()

def test_query_conversion():
    """Test the conversion of natural language to Cypher queries."""
    processor = Neo4jLLMQueryProcessor()
    
    # Test cases - natural language queries
    test_queries = [
        "Who follows Alice?",
        "Show me all posts by users who follow Bob",
        "Find accounts that have liked more than 5 posts",
        "Get posts that have been liked by people who follow each other",
        "Find the most liked post"
    ]
    
    print("\n===== TESTING NATURAL LANGUAGE TO CYPHER CONVERSION =====\n")
    
    for query in test_queries:
        print(f"Natural language: {query}")
        try:
            cypher = processor.natural_to_cypher(query)
            print(f"Cypher query: {cypher}\n")
        except Exception as e:
            print(f"Error: {str(e)}\n")
    
    processor.close()

def test_query_execution(use_real_db=False):
    """Test the execution of converted Cypher queries."""
    if not use_real_db:
        print("\n===== SKIPPING DATABASE EXECUTION TEST (use_real_db=False) =====")
        print("Set use_real_db=True to test against an actual Neo4j database")
        return
    
    processor = Neo4jLLMQueryProcessor()
    
    test_queries = [
        "Who follows Alice?",
        "Show me all posts by users who follow Bob"
    ]
    
    print("\n===== TESTING FULL QUERY PROCESSING WITH DATABASE =====\n")
    
    for query in test_queries:
        print(f"Processing: {query}")
        try:
            result = processor.process_query(query)
            print(f"Result: {json.dumps(result, indent=2)}\n")
        except Exception as e:
            print(f"Error: {str(e)}\n")
    
    processor.close()

def test_flask_app():
    """Test the Flask application (requires the app to be running)."""
    import requests
    
    base_url = "http://localhost:5000"
    
    print("\n===== TESTING FLASK API =====\n")
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Health check: {response.status_code}")
        print(response.json())
    except Exception as e:
        print(f"Health check failed: {str(e)}")
    
    # Test query conversion endpoint
    try:
        query = "Find accounts that liked posts by users who follow Alice"
        response = requests.post(
            f"{base_url}/api/convert",
            json={"query": query}
        )
        print(f"\nConvert endpoint ({query}): {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Convert endpoint failed: {str(e)}")

if __name__ == "__main__":
    test_query_conversion()
    
    # Test query execution against database
    # Change to True if you have a Neo4j database set up
    test_query_execution(use_real_db=False)
    
    # Test Flask API (requires the Flask app to be running)
    # Uncomment to test
    # test_flask_app()
