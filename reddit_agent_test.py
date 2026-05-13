"""
Reddit Scraper Agent
Searches Reddit for contractor leads using free Reddit API
Finds posts like "ISO electrician" in city subreddits
"""
import os
import time
import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class RedditScraper:
    """
    Scrapes Reddit for warm leads using free Reddit API
    No authentication needed for public posts
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ContractorLeadBot/1.0'
        })
        self.base_url = "https://www.reddit.com"
    
    def search_subreddit(
        self, 
        subreddit: str, 
        keyword: str, 
        limit: int = 25
    ) -> List[Dict]:
        """
        Search a subreddit for keyword
        
        Args:
            subreddit: Subreddit name (e.g., 'sarasota', 'florida')
            keyword: Search term (e.g., 'electrician', 'plumber')
            limit: Max results (default 25, max 100)
        
        Returns:
            List of posts with title, text, author, url, etc.
        """
        results = []
        
        # Reddit JSON API (no auth needed for public posts)
        url = f"{self.base_url}/r/{subreddit}/search.json"
        params = {
            'q': keyword,
            'limit': min(limit, 100),
            'sort': 'new',
            'restrict_sr': 'on',  # Search only this subreddit
        }
        
        try:
            time.sleep(2)  # Be polite (Reddit rate limit ~60 requests/min)
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code != 200:
                log.warning(f"Reddit returned {response.status_code}")
                return results
            
            data = response.json()
            
            for post in data.get('data', {}).get('children', []):
                post_data = post.get('data', {})
                
                # Extract post details
                result = {
                    'title': post_data.get('title', ''),
                    'selftext': post_data.get('selftext', ''),
                    'author': post_data.get('author', ''),
                    'subreddit': post_data.get('subreddit', ''),
                    'url': f"{self.base_url}{post_data.get('permalink', '')}",
                    'score': post_data.get('score', 0),
                    'num_comments': post_data.get('num_comments', 0),
                    'created_utc': post_data.get('created_utc', 0),
                    'created_datetime': datetime.fromtimestamp(
                        post_data.get('created_utc', 0)
                    ).isoformat(),
                }
                
                # Combine title and text for full content
                full_text = f"{result['title']}\n\n{result['selftext']}"
                result['full_text'] = full_text
                
                results.append(result)
            
            log.info(f"Found {len(results)} posts in r/{subreddit} for '{keyword}'")
            return results
            
        except Exception as e:
            log.error(f"Reddit search failed: {e}")
            return results
    
    def search_multiple_subreddits(
        self,
        subreddits: List[str],
        keyword: str,
        limit_per_sub: int = 10
    ) -> List[Dict]:
        """
        Search multiple subreddits for keyword
        
        Args:
            subreddits: List of subreddit names
            keyword: Search term
            limit_per_sub: Results per subreddit
        
        Returns:
            Combined list of posts from all subreddits
        """
        all_results = []
        
        for subreddit in subreddits:
            results = self.search_subreddit(subreddit, keyword, limit_per_sub)
            all_results.extend(results)
            time.sleep(2)  # Rate limiting
        
        log.info(f"Total: {len(all_results)} posts across {len(subreddits)} subreddits")
        return all_results
    
    def find_contractor_leads(
        self,
        location: str,
        trade: str = "contractor",
        include_general: bool = False
    ) -> List[Dict]:
        """SIMPLIFIED TEST VERSION - Only searches r/sarasota with 2 queries"""
        subreddits = ["sarasota"]  # Just one subreddit
        queries = [f"ISO {trade}", f"need {trade}"]  # Just 2 queries
        
        all_leads = []
        seen_urls = set()

        for query in queries:
            for subreddit in subreddits:
                results = self.search_subreddit(subreddit, query, limit=10)
                for result in results:
                    if result['url'] not in seen_urls:
                        seen_urls.add(result['url'])
                        all_leads.append(result)
                time.sleep(2)

        log.info(f"Found {len(all_leads)} unique leads for '{trade}' in {location}")
        return all_leads
    
    def _get_subreddits_for_location(self, location: str) -> List[str]:
        """
        Map location to relevant subreddits
        
        TODO: Build comprehensive location-to-subreddit mapping
        For now, returns basic city/state subreddits
        """
        location_lower = location.lower()
        
        # City-specific subreddits
        city_map = {
            'north port': ['northport', 'sarasota', 'florida'],
            'sarasota': ['sarasota', 'florida'],
            'tampa': ['tampa', 'florida'],
            'miami': ['miami', 'florida'],
            'fort myers': ['fortmyers', 'florida'],
            'seattle': ['seattle', 'washington'],
            'new york': ['nyc', 'newyork'],
            'los angeles': ['losangeles', 'california'],
        }
        
        for city, subs in city_map.items():
            if city in location_lower:
                return subs
        
        # Default: try location name + state
        return [location_lower.replace(' ', ''), 'florida']  # Assume FL if no match


# ---------------------------------------------------------------------------
# Agent Worker - Polls master controller for jobs
# ---------------------------------------------------------------------------

class RedditAgent:
    """
    Reddit scraper agent that polls master controller for jobs
    """
    
    def __init__(self, master_url: str, agent_key: str):
        self.master_url = master_url.rstrip('/')
        self.agent_key = agent_key
        self.agent_name = "reddit-agent-1"
        self.scraper = RedditScraper()
        
        log.info(f"Reddit Agent initialized: {self.agent_name}")
    
    def register(self):
        """Register agent with master controller"""
        url = f"{self.master_url}/api/agents/register"
        headers = {"X-Agent-Key": self.agent_key}
        data = {
            "name": self.agent_name,
            "agent_type": "platform3",
            "capabilities": {
                "sources": ["reddit"],
                "locations": ["all"],
            }
        }
        
        try:
            response = requests.post(url, json=data, headers=headers, timeout=10)
            if response.status_code == 200:
                log.info("Agent registered successfully")
                return True
        except Exception as e:
            log.error(f"Registration failed: {e}")
        
        return False
    
    def poll_for_job(self):
        """Poll master for next job"""
        url = f"{self.master_url}/api/jobs/next"
        headers = {"X-Agent-Key": self.agent_key}
        params = {"agent": self.agent_name}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data if data.get("job_id") else None
        except Exception as e:
            log.error(f"Poll failed: {e}")
        
        return None
    
    def execute_job(self, job: Dict) -> List[Dict]:
        """Execute scrape job"""
        keyword = job['keyword']
        location = job['location']
        
        log.info(f"Executing job: {keyword} in {location}")
        
        # Search Reddit for leads
        leads = self.scraper.find_contractor_leads(
            location=location,
            trade=keyword,
        )
        
        # Format for master controller
        results = []
        for lead in leads:
            results.append({
                'title': lead['title'],
                'description': lead.get('selftext', '')[:500],
                'post_text': lead.get('full_text'),
                'url': lead['url'],
                'posted_at': None,
            })
        
        return results
    
    def submit_results(self, job_id: int, results: List[Dict]):
        """Submit results to master"""
        url = f"{self.master_url}/api/jobs/{job_id}/submit"
        headers = {"X-Agent-Key": self.agent_key}
        data = {"results": results}
        
        try:
            response = requests.post(url, json=data, headers=headers, timeout=30)
            if response.status_code == 200:
                log.info(f"Results submitted: {len(results)} leads")
                return True
        except Exception as e:
            log.error(f"Submit failed: {e}")
        
        return False
    
    def run(self, poll_interval: int = 60):
        """Main agent loop"""
        log.info("Reddit Agent starting...")
        
        # Register
        if not self.register():
            log.error("Failed to register - exiting")
            return
        
        # Poll loop
        while True:
            try:
                job = self.poll_for_job()
                
                if job:
                    log.info(f"Received job {job.get('job_id')}")
                    
                    # Execute
                    results = self.execute_job(job)
                    
                    # Submit
                    self.submit_results(job['job_id'], results)
                else:
                    log.debug("No jobs available")
                
                # Wait before next poll
                time.sleep(poll_interval)
                
            except KeyboardInterrupt:
                log.info("Agent stopped by user")
                break
            except Exception as e:
                log.error(f"Agent error: {e}")
                time.sleep(poll_interval)


if __name__ == "__main__":
    # Configuration from environment
    MASTER_URL = os.environ.get("MASTER_URL", "http://82.25.74.217:5003")
    AGENT_KEY = os.environ.get("AGENT_KEY", "change-this-secret")
    
    # Run agent
    agent = RedditAgent(MASTER_URL, AGENT_KEY)
    agent.run(poll_interval=60)
