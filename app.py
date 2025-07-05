import os
from typing import Dict, Any, List, Optional, Union
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from NL_Query_Processor import Neo4jLLMQueryProcessor
from GraphManager import Neo4jGraphManager
from dotenv import load_dotenv
import logging
import json
from datetime import datetime
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Custom datetime converter
def datetime_converter(o):
    if isinstance(o, datetime):
        return o.strftime("%Y-%m-%d %H:%M:%S")
    if hasattr(o, 'to_native'):  # Handle Neo4j datetime
        return o.to_native().strftime("%Y-%m-%d %H:%M:%S")
    return o

# Middleware-style wrapper for jsonify
def jsonify_with_datetime(obj):
    return Response(
        json.dumps(obj, default=datetime_converter),
        mimetype='application/json'
    )

# Initialize the query processor
try:
    query_processor = Neo4jLLMQueryProcessor(
        uri=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
        openai_api_key="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",
        model_name=os.getenv("LLM_MODEL", "gpt-3.5-turbo")
    )
    logger.info("Neo4j LLM Query Processor initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Neo4j LLM Query Processor: {str(e)}")
    query_processor = None

# Initialize Neo4j manager
try:
    graph_manager = Neo4jGraphManager(
        uri=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    logger.info("Neo4j Graph Manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Neo4j Graph Manager: {str(e)}")
    graph_manager = None

# API Routes
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    if graph_manager and query_processor:
        return jsonify_with_datetime({"status": "healthy", "message": "Both Service is up and running"})
    elif graph_manager:
        return jsonify_with_datetime({"status": "healthy", "message": "graph_manager Service is up and running"})
    if query_processor:
        return jsonify_with_datetime({"status": "healthy", "message": "query_processor Service is up and running"})
    else:
        return jsonify_with_datetime({"status": "unhealthy", "message": "Service failed to initialize"}), 500

# Basic Graph Query Endpoints
@app.route("/api/graph/nodes", methods=["GET"])
def get_all_nodes():
    """Get all nodes in the graph with optional limit."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    
    limit = request.args.get("limit", default=100, type=int)
    results = graph_manager.get_all_nodes(limit)
    
    return jsonify_with_datetime({
        "nodes": results,
        "count": len(results)
    })

@app.route("/api/graph/shortest-path", methods=["POST"])
def get_shortest_path():
    """Find shortest path between two accounts."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    data = request.json

    from_name = data['from']
    to_name = data['to']
    
    if not from_name or len(from_name) == 0 or not to_name or len(to_name) == 0:
        return jsonify_with_datetime({"error": "Both 'from' and 'to' parameters are required"}), 400
    
    if from_name == to_name:
        return jsonify_with_datetime({
            "path": "[]",
            "found": 0
        })

    results = graph_manager.get_shortest_path(from_name, to_name)
    return jsonify_with_datetime({
        "path": results,
        "found": len(results) > 0
    })

@app.route("/api/graph/connections", methods=["POST"])
def get_connections():
    """Get connections of an account."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    
    data = request.json
    name = data["name"]
    depth = data["depth"]
    
    if not name or not depth or len(name) == 0:
        return jsonify_with_datetime({"error": "The 'name' parameter is required"}), 400
    
    results = graph_manager.get_account_connections(name, depth)
    
    return jsonify_with_datetime({
        "connections": results,
        "count": len(results)
    })

# Account Management Endpoints
@app.route("/api/accounts", methods=["POST"])
def add_account():
    """Add a new account."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    
    data = request.json
    if not data or "name" not in data or len(data["name"]) == 0:
        return jsonify_with_datetime({"error": "Account name is required"}), 400
    
    name = data["name"]
    # Extract additional properties excluding name
    properties = {k: v for k, v in data.items() if k != "name"}
    
    try:
        result = graph_manager.add_account(name, properties)
        return jsonify_with_datetime({
            "success": True,
            "account": result
        })
    except Exception as e:
        return jsonify_with_datetime({
            "success": False,
            "error": str(e)
        }), 400

@app.route("/api/accounts/follow", methods=["POST"])
def follow_account():
    """Create a follows relationship between accounts."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    
    data = request.json
    if not data or "follower" not in data or "followee" not in data:
        return jsonify_with_datetime({"error": "Both follower and followee names are required"}), 400
    
    try:
        result = graph_manager.follow_account(data["follower"], data["followee"])
        return jsonify_with_datetime({
            "success": True,
            "relationship": result
        })
    except Exception as e:
        return jsonify_with_datetime({
            "success": False,
            "error": str(e)
        }), 400

@app.route("/api/accounts/unfollow", methods=["POST"])
def unfollow_account():
    """Remove a follows relationship between accounts."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    
    data = request.json
    if not data or "follower" not in data or "followee" not in data:
        return jsonify_with_datetime({"error": "Both follower and followee names are required"}), 400
    
    try:
        result = graph_manager.unfollow_account(data["follower"], data["followee"])
        return jsonify_with_datetime({
            "success": True,
            "deleted": result.get("relationship_deleted", False)
        })
    except Exception as e:
        return jsonify_with_datetime({
            "success": False,
            "error": str(e)
        }), 400

# Post Management Endpoints

@app.route("/api/posts", methods=["POST"])
def add_post():
    """Add a new post for an account."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    
    data = request.json
    if not data or "account_name" not in data or "content" not in data:
        return jsonify_with_datetime({"error": "Acccount name and post content are required"}), 400
    
    post_id = data.get("post_id")  # Optional, will be generated if not provided
    
    try:
        result = graph_manager.add_post(data["account_name"], data["content"], post_id)
        return jsonify_with_datetime({
            "success": True,
            "post": result
        })
    except Exception as e:
        return jsonify_with_datetime({
            "success": False,
            "error": str(e)
        }), 400

@app.route("/api/posts/like", methods=["POST"])
def like_post():
    """Create a likes relationship between an account and a post."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    
    data = request.json
    if not data or "account_name" not in data or "post_id" not in data:
        return jsonify_with_datetime({"error": "Account name and post ID are required"}), 400
    
    try:
        result = graph_manager.like_post(data["account_name"], data["post_id"])
        return jsonify_with_datetime({
            "success": True,
            "like": result
        })
    except Exception as e:
        return jsonify_with_datetime({
            "success": False,
            "error": str(e)
        }), 400

@app.route("/api/posts/unlike", methods=["POST"])
def unlike_post():
    """Remove a likes relationship between an account and a post."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    
    data = request.json
    if not data or "account_name" not in data or "post_id" not in data:
        return jsonify_with_datetime({"error": "Account name and post ID are required"}), 400
    
    try:
        result = graph_manager.unlike_post(data["account_name"], data["post_id"])
        return jsonify_with_datetime({
            "success": True,
            "deleted": result.get("relationship_deleted", False)
        })
    except Exception as e:
        return jsonify_with_datetime({
            "success": False,
            "error": str(e)
        }), 400

@app.route("/api/accounts/<name>/posts", methods=["GET"])
def get_account_posts(name):
    """Get all posts by an account."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    
    limit = request.args.get("limit", default=50, type=int)
    skip = request.args.get("skip", default=0, type=int)
    
    try:
        results = graph_manager.get_account_posts(name, limit, skip)
        return jsonify_with_datetime({
            "account": name,
            "posts": results,
            "count": len(results)
        })
    except Exception as e:
        return jsonify_with_datetime({
            "success": False,
            "error": str(e)
        }), 400

# Advanced Query Endpoints
@app.route("/api/accounts/<name>/similar", methods=["GET"])
def find_similar_accounts(name):
    """Find similar accounts based on follow patterns and likes."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    
    limit = request.args.get("limit", default=10, type=int)
    
    try:
        results = graph_manager.find_similar_accounts(name, limit)
        return jsonify_with_datetime({
            "account": name,
            "similar_accounts": results,
            "count": len(results)
        })
    except Exception as e:
        return jsonify_with_datetime({
            "success": False,
            "error": str(e)
        }), 400

@app.route("/api/accounts/<name>/recommended-posts", methods=["GET"])
def recommend_posts(name):
    """Recommend posts for an account."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    
    limit = request.args.get("limit", default=10, type=int)
    
    try:
        results = graph_manager.recommend_posts(name, limit)
        return jsonify_with_datetime({
            "account": name,
            "recommended_posts": results,
            "count": len(results)
        })
    except Exception as e:
        return jsonify_with_datetime({
            "success": False,
            "error": str(e)
        }), 400

# PageRank and Analytics Endpoints
@app.route("/api/analytics/pagerank", methods=["GET"])
def get_pagerank():
    """Calculate and return PageRank scores for accounts."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    
    iterations = request.args.get("iterations", default=20, type=int)
    damping = request.args.get("damping", default=0.85, type=float)
    
    try:
        results = graph_manager.calculate_pagerank(iterations, damping)
        return jsonify_with_datetime({
            "pagerank_scores": results,
            "count": len(results)
        })
    except Exception as e:
        return jsonify_with_datetime({
            "success": False,
            "error": str(e)
        }), 400

@app.route("/api/analytics/statistics", methods=["GET"])
def get_statistics():
    """Get graph statistics."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    
    try:
        results = graph_manager.get_graph_statistics()
        return jsonify_with_datetime({
            "success": True,
            "statistics": results
        })
    except Exception as e:
        return jsonify_with_datetime({
            "success": False,
            "error": str(e)
        }), 400


@app.route("/api/analytics/common-connections", methods=["POST"])
def get_common_connections():
    """Get common connections between two accounts."""
    if not graph_manager:
        return jsonify_with_datetime({"error": "Graph manager not initialized"}), 500
    
    data = request.json
    if not data or "account1" not in data or "account2" not in data:
        return jsonify_with_datetime({"error": "Both account names are required"}), 400
    
    try:
        results = graph_manager.get_common_connections(data["account1"], data["account2"])
        return jsonify_with_datetime({
            "success": True,
            "common_connections": results
        })
    except Exception as e:
        return jsonify_with_datetime({
            "success": False,
            "error": str(e)
        }), 400


@app.route("/api/query", methods=["POST"])
def process_query():
    """Endpoint to process natural language queries."""
    if not query_processor:
        return jsonify_with_datetime({
            "success": False,
            "error": "Query processor is not initialized"
        }), 500
    
    data = request.json
    if not data or "query" not in data:
        return jsonify_with_datetime({
            "success": False,
            "error": "Missing 'query' field in request"
        }), 400
    
    natural_language_query = data["query"]
    # Get the profile parameter, default to False if not provided
    profile = data.get("profile", False)
    
    try:
        logger.info(f"Processing query: {natural_language_query}, with profiling: {profile}")
        result = query_processor.process_query(natural_language_query, profile=profile)
        return jsonify_with_datetime(result)
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return jsonify_with_datetime({
            "success": False,
            "error": str(e),
            "natural_language_query": natural_language_query
        }), 500

@app.route("/api/convert", methods=["POST"])
def convert_to_cypher():
    """Endpoint to only convert natural language to Cypher without execution."""
    if not query_processor:
        return jsonify_with_datetime({
            "success": False,
            "error": "Query processor is not initialized"
        }), 500
    
    data = request.json
    if not data or "query" not in data:
        return jsonify_with_datetime({
            "success": False,
            "error": "Missing 'query' field in request"
        }), 400
    
    natural_language_query = data["query"]
    
    try:
        logger.info(f"Converting query to Cypher: {natural_language_query}")
        cypher_query = query_processor.natural_to_cypher(natural_language_query)
        return jsonify_with_datetime({
            "success": True,
            "natural_language_query": natural_language_query,
            "cypher_query": cypher_query
        })
    except Exception as e:
        logger.error(f"Error converting query: {str(e)}")
        return jsonify_with_datetime({
            "success": False,
            "error": str(e),
            "natural_language_query": natural_language_query
        }), 500

@app.route("/api/profile", methods=["POST"])
def profile_query():
    """Endpoint to profile a Cypher query execution."""
    if not query_processor:
        return jsonify_with_datetime({
            "success": False,
            "error": "Query processor is not initialized"
        }), 500
    
    data = request.json
    if not data or "query" not in data:
        return jsonify_with_datetime({
            "success": False,
            "error": "Missing 'query' field in request"
        }), 400
    
    natural_language_query = data["query"]
    
    try:
        logger.info(f"Profiling query: {natural_language_query}")
        # Force profiling to be enabled
        result = query_processor.process_query(natural_language_query, profile=True)
        return jsonify_with_datetime(result)
    except Exception as e:
        logger.error(f"Error profiling query: {str(e)}")
        return jsonify_with_datetime({
            "success": False,
            "error": str(e),
            "natural_language_query": natural_language_query
        }), 500

@app.route("/api/execute-cypher", methods=["POST"])
def execute_cypher():
    """Endpoint to directly execute a Cypher query with optional profiling."""
    if not query_processor:
        return jsonify_with_datetime({
            "success": False,
            "error": "Query processor is not initialized"
        }), 500
    
    data = request.json
    if not data or "cypher" not in data:
        return jsonify_with_datetime({
            "success": False,
            "error": "Missing 'cypher' field in request"
        }), 400
    
    cypher_query = data["cypher"]
    profile = data.get("profile", False)
    params = data.get("params", {})
    
    try:
        logger.info(f"Executing Cypher query: {cypher_query}, with profiling: {profile}")
        
        if profile:
            execution_data = query_processor.execute_profiled_cypher(cypher_query, params)
            result = {
                "cypher_query": cypher_query,
                "results": execution_data["results"],
                "profile_text": execution_data["profile_text"],
                "success": True
            }
        else:
            results = query_processor.execute_cypher(cypher_query, params)
            result = {
                "cypher_query": cypher_query,
                "results": results,
                "success": True
            }
        
        return jsonify_with_datetime(result)
    except Exception as e:
        logger.error(f"Error executing Cypher query: {str(e)}")
        return jsonify_with_datetime({
            "success": False,
            "error": str(e),
            "cypher_query": cypher_query
        }), 500

@app.teardown_appcontext
def cleanup(exception=None):
    """Clean up resources when the application context ends."""
    if graph_manager:
        graph_manager.close()

if __name__ == "__main__":
    port = 5002
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "False").lower() == "true")
