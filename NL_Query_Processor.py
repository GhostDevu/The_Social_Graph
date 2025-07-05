import os
import re
from typing import Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from neo4j import GraphDatabase
from dotenv import load_dotenv
import json

load_dotenv()  # Load environment variables from .env file

class Neo4jLLMQueryProcessor:
    """A class to process natural language into Cypher queries for Neo4j."""
    
    def __init__(
        self, 
        uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        username: str = os.getenv("NEO4J_USERNAME", "neo4j"),
        password: str = os.getenv("NEO4J_PASSWORD", "password"),
        openai_api_key: str = os.getenv("OPENAI_API_KEY"),
        model_name: str = "gpt-3.5-turbo",
        temperature: float = 0.0  # Low temperature for more deterministic output
    ):
        """Initialize with Neo4j connection details and LLM configuration."""
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        
        # Define the schema information
        self.schema = """
            Database schema:
            Account : {name STRING, ...}
            Post : {post_id ID, post_content STRING}

            Relationships:
            Account [Follows] Account
            Account [Posts] Post
            Account [Likes] Post
        """

        self.examples = """
            Example 1:
            Natural language query: Find all accounts that follow 'Alice'
            Cypher query: MATCH (a:Account)-[:Follows]->(b:Account {name: 'Alice'}) RETURN a.name

            Example 2:
            Natural language query: Show me posts liked by users who follow 'Bob'
            Cypher query: MATCH (a:Account)-[:Follows]->(:Account {name: 'Bob'}), (a)-[:Likes]->(p:Post) RETURN p.post_content

            Example 3:
            Natural language query: Which accounts have the most followers?
            Cypher query: MATCH (follower:Account)-[:Follows]->(a:Account) WITH a, COUNT(follower) AS followerCount RETURN a.name, followerCount ORDER BY followerCount DESC LIMIT 10
            
            Example 4:
            Natural language query: Find accounts that both post and like content
            Cypher query: MATCH (a:Account)-[:Posts]->(:Post), (a)-[:Likes]->(:Post) RETURN DISTINCT a.name
        """

        # Create the LLM chain
        self.llm = ChatOllama(
            model="mistral",  
            temperature=temperature
        )

        self.prompt_template = ChatPromptTemplate.from_template("""
            You are an expert Neo4j Cypher query generator.
            
            Given the following Neo4j graph database schema:
            {schema}
            
            Here are some examples of natural language queries and their corresponding Cypher queries:
            {examples}
                                                                
            Your task is to convert the following natural language query into a valid Cypher query.
            Return only the Cypher query with no explanations or markdown.
            
            Natural language query: {query}
            
            Cypher query:
            """
        )
        
        self.chain = self.prompt_template | self.llm | StrOutputParser()
    
    def natural_to_cypher(self, query: str) -> str:
        """Convert natural language query to Cypher query."""
        return self.chain.invoke({"schema": self.schema, "examples": self.examples, "query": query})
    
    def execute_cypher(self, cypher_query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a Cypher query on the Neo4j database."""
        if params is None:
            params = {}
            
        with self.driver.session() as session:
            result = session.run(cypher_query, params)
            return [record.data() for record in result]
    
    def execute_profiled_cypher(self, cypher_query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a profiled Cypher query and return both results and profile metrics."""
        if params is None:
            params = {}
            
        # Add PROFILE to the query
        profiled_query = f"PROFILE {cypher_query}"
        
        with self.driver.session() as session:
            result = session.run(profiled_query, params)
            results = [record.data() for record in result]
            
            # Get profile summary
            summary = result.consume()
            profile_string = summary.profile
            
            return {
                "results": results,
                "profile_text": profile_string
            }
    
    def parse_profile_metrics(self, profile_string: str) -> Dict[str, Any]:
        """Parse Neo4j query profile string and extract key metrics."""
        metrics = {
            "db_hits": 0,
            "rows": 0,
            "elapsed_time_ms": 0,
            "memory_usage": "",
            "operators": [],
            "total_db_hits": 0,
            "query_time_ms": 0,
            "planning_time_ms": 0,
            "indexes_used": [],
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # Extract overall execution time
        time_match = re.search(r"Cypher version:.+, planner: \w+, runtime: \w+\. (\d+) total db hits in (\d+\.\d+) ms\.", 
                           profile_string, re.DOTALL)
        if time_match:
            metrics["total_db_hits"] = int(time_match.group(1))
            metrics["query_time_ms"] = float(time_match.group(2))
        
        # Extract planning time
        planning_match = re.search(r"planning: (\d+\.\d+) ms", profile_string)
        if planning_match:
            metrics["planning_time_ms"] = float(planning_match.group(1))
        
        # Extract memory usage
        memory_match = re.search(r"memory\s*\[\s*([\d\.]+\s*[KMG]B)\s*\]", profile_string, re.IGNORECASE)
        if memory_match:
            metrics["memory_usage"] = memory_match.group(1)
        
        # Extract operator statistics
        operators = []
        operator_blocks = re.findall(r"\+\-*([^+]+?)(?=\+|$)", profile_string, re.DOTALL)
        
        for block in operator_blocks:
            operator_name = ""
            name_match = re.search(r"([A-Za-z]+)", block)
            if name_match:
                operator_name = name_match.group(1)
            
            db_hits = 0
            db_hits_match = re.search(r"db hits\s*\[\s*(\d+)\s*\]", block, re.IGNORECASE)
            if db_hits_match:
                db_hits = int(db_hits_match.group(1))
                metrics["db_hits"] += db_hits
            
            rows = 0
            rows_match = re.search(r"rows\s*\[\s*(\d+)\s*\]", block, re.IGNORECASE)
            if rows_match:
                rows = int(rows_match.group(1))
                # Update the total rows with the last operation's rows (typically the output)
                metrics["rows"] = rows
            
            elapsed = 0
            elapsed_match = re.search(r"elapsed\s*\[\s*(\d+)\s*ms\s*\]", block, re.IGNORECASE)
            if elapsed_match:
                elapsed = int(elapsed_match.group(1))
                metrics["elapsed_time_ms"] = max(metrics["elapsed_time_ms"], elapsed)
            
            # Check for index usage
            index_match = re.search(r"(Index|NodeIndexSeek).+\((.+?)\)", block, re.IGNORECASE)
            if index_match and index_match.group(2) not in metrics["indexes_used"]:
                metrics["indexes_used"].append(index_match.group(2))
            
            operators.append({
                "name": operator_name,
                "db_hits": db_hits,
                "rows": rows,
                "elapsed_ms": elapsed
            })
        
        metrics["operators"] = operators
        
        # Extract cache information
        cache_hits_match = re.search(r"cache hits: (\d+)", profile_string, re.IGNORECASE)
        if cache_hits_match:
            metrics["cache_hits"] = int(cache_hits_match.group(1))
        
        cache_misses_match = re.search(r"cache misses: (\d+)", profile_string, re.IGNORECASE)
        if cache_misses_match:
            metrics["cache_misses"] = int(cache_misses_match.group(1))
            
        return metrics
    
    def process_query(self, natural_language_query: str, profile: bool = False) -> Dict[str, Any]:
        """Process a natural language query to Cypher and execute it with optional profiling."""
        try:
            cypher_query = self.natural_to_cypher(natural_language_query)
            
            if profile:
                execution_data = self.execute_profiled_cypher(cypher_query)
                del execution_data["profile_text"]["args"]["string-representation"] 
                return {
                    "profile":{
                        "natural_language_query": natural_language_query,
                        "cypher_query": cypher_query,
                        "results": execution_data["results"],
                        "profile_text": execution_data["profile_text"]
                    },
                    "success": True
                }
            else:
                results = self.execute_cypher(cypher_query)
                return {
                    "profile":{   
                        "natural_language_query": natural_language_query,
                        "cypher_query": cypher_query,
                        "results": results
                    },
                    "success": True
                }
        except Exception as e:
            return {
                "natural_language_query": natural_language_query,
                "error": str(e),
                "success": False
            }
    
    def close(self):
        """Close the Neo4j connection."""
        self.driver.close()
