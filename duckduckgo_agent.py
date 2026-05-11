"""
DuckDuckGo Scraper Agent
Generic keyword search using DuckDuckGo HTML
Proven to work with no rate limiting
"""
import os
import time
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from urllib.parse import quote_plus

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class DuckDuckGoScraper:
    """
    Scrapes DuckDuckGo for any keyword
    No API key needed, no rate limits detected
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def search(self, keyword: str, location: str = "", num_results: int = 10) -> List[Dict]:
        """
        Search DuckDuckGo for keyword + location
        
        Args:
            keyword: Search term (e.g., "electrician")
            location: Location (e.g., "North Port FL")
            num_results: Max results to return
        
        Returns:
            List of search results
        """
        # Build query
        if location:
            query = f"{keyword} {location}"
        else:
            query = keyword
        
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        
        try:
            response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                log.warning(f"DuckDuckGo returned {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            results = []
            result_divs = soup.find_all('div', class_='result')[:num_results]
            
            for div in result_divs:
                try:
                    # Extract title
                    title_tag = div.find('a', class_='result__a')
                    if not title_tag:
                        continue
                    
                    title = title_tag.get_text(strip=True)
                    url_href = title_tag.get('href', '')
                    
                    # Extract snippet
                    snippet_tag = div.find('a', class_='result__snippet')
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    
                    results.append({
                        'title': title,
                        'url': url_href,
                        'description': snippet,
                        'source': 'duckduckgo',
                    })
                    
                except Exception as e:
                    log.debug(f"Error parsing result: {e}")
                    continue
            
            log.info(f"DuckDuckGo: Found {len(results)} results for '{query}'")
            return results
            
        except Exception as e:
            log.error(f"DuckDuckGo search failed: {e}")
            return []


class DuckDuckGoAgent:
    """
    DuckDuckGo scraper agent - polls master for jobs
    """
    
    def __init__(self, master_url: str, agent_key: str):
        self.master_url = master_url.rstrip('/')
        self.agent_key = agent_key
        self.agent_name = "duckduckgo-agent-1"
        self.scraper = DuckDuckGoScraper()
        
        log.info(f"DuckDuckGo Agent initialized: {self.agent_name}")
    
    def register(self):
        """Register with master"""
        url = f"{self.master_url}/api/agents/register"
        headers = {"X-Agent-Key": self.agent_key}
        data = {
            "name": self.agent_name,
            "agent_type": "platform3",
            "capabilities": {
                "sources": ["duckduckgo"],
                "locations": ["all"],
            }
        }
        
        try:
            response = requests.post(url, json=data, headers=headers, timeout=10)
            if response.status_code == 200:
                log.info("Agent registered")
                return True
        except Exception as e:
            log.error(f"Registration failed: {e}")
        
        return False
    
    def poll_for_job(self):
        """Poll for next job"""
        url = f"{self.master_url}/api/jobs/next"
        headers = {"X-Agent-Key": self.agent_key}
        params = {"agent": self.agent_name}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json().get("job")
        except Exception as e:
            log.error(f"Poll failed: {e}")
        
        return None
    
    def execute_job(self, job: Dict) -> List[Dict]:
        """Execute search job"""
        keyword = job['keyword']
        location = job['location']
        
        log.info(f"Searching: {keyword} in {location}")
        
        results = self.scraper.search(keyword, location, num_results=10)
        
        # Format for master
        formatted = []
        for result in results:
            formatted.append({
                'title': result['title'],
                'description': result['description'],
                'url': result['url'],
                'post_text': result['description'],  # DuckDuckGo doesn't have full text
            })
        
        return formatted
    
    def submit_results(self, job_id: int, results: List[Dict]):
        """Submit results"""
        url = f"{self.master_url}/api/jobs/{job_id}/submit"
        headers = {"X-Agent-Key": self.agent_key}
        data = {"results": results}
        
        try:
            response = requests.post(url, json=data, headers=headers, timeout=30)
            if response.status_code == 200:
                log.info(f"Submitted {len(results)} results")
                return True
        except Exception as e:
            log.error(f"Submit failed: {e}")
        
        return False
    
    def run(self, poll_interval: int = 60):
        """Main loop"""
        log.info("DuckDuckGo Agent starting...")
        
        if not self.register():
            log.error("Failed to register")
            return
        
        while True:
            try:
                job = self.poll_for_job()
                
                if job:
                    results = self.execute_job(job)
                    self.submit_results(job['job_id'], results)
                else:
                    log.debug("No jobs")
                
                time.sleep(poll_interval)
                
            except KeyboardInterrupt:
                log.info("Stopped")
                break
            except Exception as e:
                log.error(f"Error: {e}")
                time.sleep(poll_interval)


if __name__ == "__main__":
    MASTER_URL = os.environ.get("MASTER_URL", "http://82.25.74.217:5003")
    AGENT_KEY = os.environ.get("AGENT_KEY", "change-this-secret")
    
    agent = DuckDuckGoAgent(MASTER_URL, AGENT_KEY)
    agent.run()
