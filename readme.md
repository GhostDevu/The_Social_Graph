# The_Social_Graph

## Overview

**The_Social_Graph** is a full-stack, AI-powered social network analytics platform built on top of a Neo4j graph database. It enables advanced querying, analytics, and visualization of large-scale social networks (e.g., Twitter, Facebook, Congress) using both traditional graph algorithms and natural language (LLM) interfaces. The project supports importing real-world datasets, managing accounts and posts, and running analytics such as PageRank, shortest paths, and viral centrality. It exposes a robust REST API for programmatic access and includes a natural language query processor that translates user questions into Cypher queries using LLMs.

---

## Key Features & Technical Achievements

- **Graph Database Backend:** Uses Neo4j to store and query social network data (accounts, posts, relationships).
- **Flexible Data Import:** Supports multiple real-world datasets (Twitter, Facebook, Congress) with scripts for parsing and loading.
- **RESTful API:** Exposes endpoints for graph queries, account/post management, analytics, and recommendations.
- **Natural Language Querying:** Integrates LLMs (OpenAI, Ollama, LangChain) to convert user questions into Cypher queries.
- **Graph Analytics:** Implements PageRank, shortest path, similarity, recommendations, and viral centrality.
- **Test Suite:** Includes unit and integration tests for API and database logic.
- **Container/Environment Ready:** Uses `.env`/`DBMS_aura_key.txt` for secure database credentials.
- **Dataset Exploration:** Includes scripts and documentation for exploring and analyzing large social datasets.

---

## Database Structure

### Node Types
- **Account**: Represents a user. Properties: `name` (unique), plus arbitrary profile fields.
- **Post**: Represents a post. Properties: `post_id` (unique), `post_content`, `timestamp`.

### Relationship Types
- **FOLLOWS**: `(Account)-[:Follows]->(Account)` — directed, represents a follow.
- **POSTS**: `(Account)-[:Posts]->(Post)` — directed, user creates a post.
- **LIKES**: `(Account)-[:Likes]->(Post)` — directed, user likes a post.

### Constraints & Indexes
- Unique constraint on `Account.name` and `Post.post_id`.
- Index on `Post.timestamp` for efficient queries.

---

## Datasets & Data Structure

### Main Datasets (in `load_data/`)
- **congress_network/**: Congressional Twitter network (see `README.txt` inside for details, includes weighted/directed edges, usernames, and viral centrality scripts).
- **facebook/**: Ego networks from Facebook (see `readme.txt` for file formats: `.edges`, `.circles`, `.feat`, `.egofeat`, `.featnames`).
- **twitter/**: Ego networks from Twitter (similar structure to Facebook, but edges are directed).
- **facebook_combined.txt**, **twitter_combined.txt**: Large combined edge lists for bulk import.

#### Example: Facebook/Twitter Ego Network Files
- `nodeId.edges`: Edges in the ego network for nodeId.
- `nodeId.circles`: Circles (groups) for the ego node.
- `nodeId.feat`: Features for each node.
- `nodeId.egofeat`: Features for the ego user.
- `nodeId.featnames`: Names of feature dimensions.

#### Example: Congress Network
- `congress_network_data.json`: Lists of in/out connections, weights, and usernames.
- `congress.edgelist`: Weighted, directed edge list (NetworkX format).
- `compute_vc.py`, `viral_centrality.py`: Scripts for viral centrality analysis.

---

## Application Structure & Main Files

- `app.py`: Main Flask API server. Exposes all REST endpoints and initializes the database and LLM query processor.
- `GraphManager.py`: Handles all Neo4j database operations (CRUD, analytics, recommendations).
- `NL_Query_Processor.py`: Converts natural language queries to Cypher using LLMs (OpenAI, Ollama, LangChain).
- `make_own_dataset.py`: Script to generate or preprocess custom datasets.
- `test.py`: Unit and integration tests for API/database logic.
- `curl file.txt`: Example curl commands for API usage.
- `requirements.txt`: Python dependencies.
- `DBMS_aura_key.txt`: Example .env file for Neo4j Aura credentials.
- `graph_input_format.txt`: Example input format for graph visualization components.

---

## Setup & Installation

1. **Clone the repository:**
   ```sh
   git clone <repo-url>
   cd The_Social_Graph
   ```
2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
3. **Configure Neo4j connection:**
   - Edit `DBMS_aura_key.txt` or set environment variables:
     - `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
   - (Optional) Set `OPENAI_API_KEY` for LLM-powered queries.
4. **(Optional) Import datasets:**
   - Use scripts in `load_data/` or `make_own_dataset.py` to load data into Neo4j.
5. **Run the server:**
   ```sh
   python app.py
   # By default, runs on http://127.0.0.1:5002
   ```

---

## API Usage Examples

See `curl file.txt` for full examples. Here are some highlights:

- **Health check:**
  ```sh
  curl http://127.0.0.1:5002/health
  ```
- **Get all nodes:**
  ```sh
  curl http://127.0.0.1:5002/api/graph/nodes
  ```
- **Find shortest path:**
  ```sh
  curl -X POST http://127.0.0.1:5002/api/graph/shortest-path \
    -H 'Content-Type: application/json' \
    -d '{"from": "alice", "to": "bob"}'
  ```
- **Add account:**
  ```sh
  curl -X POST http://127.0.0.1:5002/api/accounts \
    -H 'Content-Type: application/json' \
    -d '{"name": "Janice"}'
  ```
- **Follow account:**
  ```sh
  curl -X POST http://127.0.0.1:5002/api/accounts/follow \
    -H 'Content-Type: application/json' \
    -d '{"follower": "alice", "followee": "bob"}'
  ```
- **Natural language query:**
  ```sh
  curl -X POST http://127.0.0.1:5003/api/query \
    -H 'Content-Type: application/json' \
    -d '{"query": "who follows alice?"}'
  ```

---

## Natural Language Querying

- The `/api/query` endpoint accepts English questions and returns Cypher + results.
- Powered by LLMs (OpenAI, Ollama, LangChain). See `NL_Query_Processor.py` for details.

---

## Testing

- Run all tests:
  ```sh
  python -m unittest test.py
  ```

---

## References & Further Reading
- See `The_deepseekers_v1.pdf` for project report and technical background.
---

**Author:** Devanshu Agrawal
