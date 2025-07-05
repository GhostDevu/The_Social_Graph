import unittest
import json
import os
from unittest.mock import patch, MagicMock
from flask import Flask
from neo4j import GraphDatabase, Result

# Import the application code
from app import app, Neo4jGraphManager, graph_manager

class MockRecord:
    def __init__(self, data_dict):
        self._data = data_dict
    
    def data(self):
        return self._data

class MockResult:
    def __init__(self, data_list):
        self._data = [MockRecord(item) for item in data_list]
    
    def __iter__(self):
        return iter(self._data)

class TestNeo4jGraphManager(unittest.TestCase):
    """Test cases for Neo4jGraphManager class."""
    
    @patch.object(GraphDatabase, 'driver')
    def setUp(self, mock_driver):
        """Set up test environment."""
        self.mock_driver = mock_driver
        self.mock_session = MagicMock()
        self.mock_driver.session.return_value = self.mock_session
        
        # Create a context manager mock for the session
        self.mock_session.__enter__ = MagicMock(return_value=self.mock_session)
        self.mock_session.__exit__ = MagicMock(return_value=None)
        
        # Create the graph manager
        self.graph_manager = Neo4jGraphManager(
            uri="bolt://mock:7687",
            username="test",
            password="test"
        )
    
    def test_init(self):
        """Test initialization of the graph manager."""
        self.assertIsNotNone(self.graph_manager)
        self.assertEqual(self.mock_driver.session.call_count, 2)  # Constraints and indexes
    
    def test_execute_query(self):
        """Test execute_query method."""
        mock_data = [{"name": "Test"}]
        self.mock_session.run.return_value = MockResult(mock_data)
        
        result = self.graph_manager.execute_query("MATCH (n) RETURN n", {"param": "value"})
        
        self.mock_session.run.assert_called_with("MATCH (n) RETURN n", {"param": "value"})
        self.assertEqual(result, mock_data)
    
    def test_add_account(self):
        """Test add_account method."""
        mock_data = [{"a": {"name": "TestUser", "bio": "Test Bio"}}]
        self.mock_session.run.return_value = MockResult(mock_data)
        
        result = self.graph_manager.add_account("TestUser", {"bio": "Test Bio"})
        
        self.mock_session.run.assert_called_with(
            """
        CREATE (a:Account $properties)
        RETURN a
        """,
            {"properties": {"name": "TestUser", "bio": "Test Bio"}}
        )
        self.assertEqual(result, mock_data[0])
    
    def test_follow_account(self):
        """Test follow_account method."""
        mock_data = [{"follower": {"name": "User1"}, "followee": {"name": "User2"}, "r": {}}]
        self.mock_session.run.return_value = MockResult(mock_data)
        
        result = self.graph_manager.follow_account("User1", "User2")
        
        self.assertEqual(result, mock_data[0])
    
    def test_add_post(self):
        """Test add_post method."""
        mock_data = [{"a": {"name": "User1"}, "p": {"post_id": "123", "post_content": "Test post"}, "r": {}}]
        self.mock_session.run.return_value = MockResult(mock_data)
        
        result = self.graph_manager.add_post("User1", "Test post", "123")
        
        self.assertEqual(result, mock_data[0])
    
    def test_like_post(self):
        """Test like_post method."""
        mock_data = [{"a": {"name": "User1"}, "p": {"post_id": "123"}, "r": {}}]
        self.mock_session.run.return_value = MockResult(mock_data)
        
        result = self.graph_manager.like_post("User1", "123")
        
        self.assertEqual(result, mock_data[0])
    
    def test_find_similar_accounts(self):
        """Test find_similar_accounts method."""
        mock_data = [
            {"similar_account": "User2", "common_follows": 3, "common_likes": 2, "similarity_score": 5},
            {"similar_account": "User3", "common_follows": 2, "common_likes": 2, "similarity_score": 4}
        ]
        self.mock_session.run.return_value = MockResult(mock_data)
        
        result = self.graph_manager.find_similar_accounts("User1")
        
        self.assertEqual(result, mock_data)
    
    def test_recommend_posts(self):
        """Test recommend_posts method."""
        mock_data = [
            {"post_id": "123", "content": "Test post 1", "recommendation_score": 3.5},
            {"post_id": "456", "content": "Test post 2", "recommendation_score": 2.0}
        ]
        self.mock_session.run.return_value = MockResult(mock_data)
        
        result = self.graph_manager.recommend_posts("User1")
        
        self.assertEqual(result, mock_data)
    
    def test_calculate_pagerank(self):
        """Test calculate_pagerank method."""
        # Test successful GDS case
        mock_data = [
            {"account": "User1", "pagerank": 0.5},
            {"account": "User2", "pagerank": 0.3}
        ]
        self.mock_session.run.return_value = MockResult(mock_data)
        
        result = self.graph_manager.calculate_pagerank()
        
        self.assertEqual(result, mock_data)
        
        # Test fallback case when GDS fails
        self.mock_session.run.side_effect = [Exception("GDS not available"), MockResult([{"nodes": 2}])]
        
        with patch.object(Neo4jGraphManager, '_custom_pagerank_implementation') as mock_custom:
            mock_custom.return_value = [{"account": "User1", "pagerank": 0.5}]
            result = self.graph_manager.calculate_pagerank()
            mock_custom.assert_called_once()
            self.assertEqual(result, [{"account": "User1", "pagerank": 0.5}])


class TestFlaskAPI(unittest.TestCase):
    """Test cases for Flask API endpoints."""
    
    def setUp(self):
        """Set up test environment."""
        self.app = app.test_client()
        self.app.testing = True
    
    @patch('app.graph_manager')
    def test_health_check(self, mock_graph_manager):
        """Test health check endpoint."""
        response = self.app.get('/health')
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'healthy')
    
    @patch('app.graph_manager')
    def test_get_all_nodes(self, mock_graph_manager):
        """Test get_all_nodes endpoint."""
        mock_nodes = [{"n": {"name": "Test"}, "node_type": ["Account"]}]
        mock_graph_manager.get_all_nodes.return_value = mock_nodes
        
        response = self.app.get('/api/graph/nodes?limit=10')
        data = json.loads(response.data)
        
        mock_graph_manager.get_all_nodes.assert_called_with(10)
        self.assertEqual(data['nodes'], mock_nodes)
        self.assertEqual(data['count'], len(mock_nodes))
    
    @patch('app.graph_manager')
    def test_add_account(self, mock_graph_manager):
        """Test add_account endpoint."""
        account_data = {"name": "TestUser", "bio": "Test bio"}
        mock_graph_manager.add_account.return_value = {"a": account_data}
        
        response = self.app.post(
            '/api/accounts',
            data=json.dumps(account_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        mock_graph_manager.add_account.assert_called_with("TestUser", {"bio": "Test bio"})
        self.assertTrue(data['success'])
        self.assertEqual(data['account'], {"a": account_data})
    
    @patch('app.graph_manager')
    def test_follow_account(self, mock_graph_manager):
        """Test follow_account endpoint."""
        follow_data = {"follower": "User1", "followee": "User2"}
        mock_result = {"follower": {"name": "User1"}, "followee": {"name": "User2"}}
        mock_graph_manager.follow_account.return_value = mock_result
        
        response = self.app.post(
            '/api/accounts/follow',
            data=json.dumps(follow_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        mock_graph_manager.follow_account.assert_called_with("User1", "User2")
        self.assertTrue(data['success'])
        self.assertEqual(data['relationship'], mock_result)
    
    @patch('app.graph_manager')
    def test_add_post(self, mock_graph_manager):
        """Test add_post endpoint."""
        post_data = {"account_name": "User1", "content": "Test post"}
        mock_result = {"a": {"name": "User1"}, "p": {"post_content": "Test post"}}
        mock_graph_manager.add_post.return_value = mock_result
        
        response = self.app.post(
            '/api/posts',
            data=json.dumps(post_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        mock_graph_manager.add_post.assert_called_with("User1", "Test post", None)
        self.assertTrue(data['success'])
        self.assertEqual(data['post'], mock_result)
    
    @patch('app.graph_manager')
    def test_like_post(self, mock_graph_manager):
        """Test like_post endpoint."""
        like_data = {"account_name": "User1", "post_id": "123"}
        mock_result = {"a": {"name": "User1"}, "p": {"post_id": "123"}}
        mock_graph_manager.like_post.return_value = mock_result
        
        response = self.app.post(
            '/api/posts/like',
            data=json.dumps(like_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        mock_graph_manager.like_post.assert_called_with("User1", "123")
        self.assertTrue(data['success'])
        self.assertEqual(data['like'], mock_result)
    
    @patch('app.graph_manager')
    def test_get_account_posts(self, mock_graph_manager):
        """Test get_account_posts endpoint."""
        mock_posts = [
            {"post_id": "123", "post_content": "Post 1"},
            {"post_id": "456", "post_content": "Post 2"}
        ]
        mock_graph_manager.get_account_posts.return_value = mock_posts
        
        response = self.app.get('/api/accounts/User1/posts?limit=10&skip=0')
        data = json.loads(response.data)
        
        mock_graph_manager.get_account_posts.assert_called_with("User1", 10, 0)
        self.assertEqual(data['account'], "User1")
        self.assertEqual(data['posts'], mock_posts)
        self.assertEqual(data['count'], len(mock_posts))
    
    @patch('app.graph_manager')
    def test_find_similar_accounts(self, mock_graph_manager):
        """Test find_similar_accounts endpoint."""
        mock_similar = [
            {"similar_account": "User2", "similarity_score": 5},
            {"similar_account": "User3", "similarity_score": 4}
        ]
        mock_graph_manager.find_similar_accounts.return_value = mock_similar
        
        response = self.app.get('/api/accounts/User1/similar?limit=5')
        data = json.loads(response.data)
        
        mock_graph_manager.find_similar_accounts.assert_called_with("User1", 5)
        self.assertEqual(data['account'], "User1")
        self.assertEqual(data['similar_accounts'], mock_similar)
    
    @patch('app.graph_manager')
    def test_recommend_posts(self, mock_graph_manager):
        """Test recommend_posts endpoint."""
        mock_recommendations = [
            {"post_id": "123", "content": "Post 1", "recommendation_score": 3.5},
            {"post_id": "456", "content": "Post 2", "recommendation_score": 2.0}
        ]
        mock_graph_manager.recommend_posts.return_value = mock_recommendations
        
        response = self.app.get('/api/accounts/User1/recommended-posts?limit=5')
        data = json.loads(response.data)
        
        mock_graph_manager.recommend_posts.assert_called_with("User1", 5)
        self.assertEqual(data['account'], "User1")
        self.assertEqual(data['recommended_posts'], mock_recommendations)
    
    @patch('app.graph_manager')
    def test_get_pagerank(self, mock_graph_manager):
        """Test get_pagerank endpoint."""
        mock_pagerank = [
            {"account": "User1", "pagerank": 0.5},
            {"account": "User2", "pagerank": 0.3}
        ]
        mock_graph_manager.calculate_pagerank.return_value = mock_pagerank
        
        response = self.app.get('/api/analytics/pagerank?iterations=30&damping=0.9')
        data = json.loads(response.data)
        
        mock_graph_manager.calculate_pagerank.assert_called_with(30, 0.9)
        self.assertEqual(data['pagerank_scores'], mock_pagerank)
    
    @patch('app.graph_manager')
    def test_get_influential_paths(self, mock_graph_manager):
        """Test get_influential_paths endpoint."""
        mock_paths = [{"path": "path_data", "path_weight": 0.8}]
        mock_graph_manager.find_influential_paths.return_value = mock_paths
        
        response = self.app.get('/api/analytics/influential-paths?from=User1&to=User2')
        data = json.loads(response.data)
        
        mock_graph_manager.find_influential_paths.assert_called_with("User1", "User2")
        self.assertEqual(data['from'], "User1")
        self.assertEqual(data['to'], "User2")
        self.assertEqual(data['paths'], mock_paths)


class TestErrorHandling(unittest.TestCase):
    """Test cases for error handling in API endpoints."""
    
    def setUp(self):
        """Set up test environment."""
        self.app = app.test_client()
        self.app.testing = True
    
    @patch('app.graph_manager')
    def test_missing_parameters(self, mock_graph_manager):
        """Test handling of missing parameters."""
        # Test missing name in add_account
        response = self.app.post(
            '/api/accounts',
            data=json.dumps({"bio": "Test bio"}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        # Test missing parameters in follow_account
        response = self.app.post(
            '/api/accounts/follow',
            data=json.dumps({"follower": "User1"}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        # Test missing parameters in add_post
        response = self.app.post(
            '/api/posts',
            data=json.dumps({"account_name": "User1"}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
    
    @patch('app.graph_manager')
    def test_database_exceptions(self, mock_graph_manager):
        """Test handling of database exceptions."""
        mock_graph_manager.add_account.side_effect = Exception("Database error")
        
        response = self.app.post(
            '/api/accounts',
            data=json.dumps({"name": "TestUser"}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 400)
        self.assertFalse(data['success'])
        self.assertIn('error', data)


if __name__ == '__main__':
    unittest.main()