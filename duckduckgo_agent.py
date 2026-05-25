"""
DuckDuckGo Scraper Agent — uses ddgs library (no HTML scraping, no captcha)
"""
import os
import time
import logging
import requests
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class DuckDuckGoScraper:
    def search(self, keyword: str, location: str = "", num_results: int = 10) -> List[Dict]:
        from ddgs import DDGS
        query = f"{keyword} {location}".strip()
        try:
            results = []
            with DDGS() as d:
                for r in d.text(query, max_results=num_results):
                    results.append({
                        'title': r.get('title', ''),
                        'url': r.get('href', ''),
                        'description': r.get('body', ''),
                        'source': 'duckduckgo',
                    })
            log.info(f"DDG: {len(results)} results for '{query}'")
            time.sleep(1)
            return results
        except Exception as e:
            log.error(f"DDG search failed: {e}")
            return []


class DuckDuckGoAgent:
    def __init__(self, master_url: str, agent_key: str):
        self.master_url = master_url.rstrip('/')
        self.agent_key = agent_key
        self.agent_name = "duckduckgo-agent-1"
        self.scraper = DuckDuckGoScraper()
        log.info(f"DuckDuckGo Agent initialized: {self.agent_name}")

    def register(self):
        url = f"{self.master_url}/api/agents/register"
        headers = {"X-Agent-Key": self.agent_key}
        data = {
            "name": self.agent_name,
            "agent_type": "platform3",
            "capabilities": {"sources": ["duckduckgo"], "locations": ["all"]}
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
        url = f"{self.master_url}/api/jobs/next"
        headers = {"X-Agent-Key": self.agent_key}
        params = {"agent": self.agent_name, "source": "duckduckgo"}
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                d = response.json()
                return d if d.get("job_id") else None
        except Exception as e:
            log.error(f"Poll failed: {e}")
        return None

    def execute_job(self, job: Dict) -> List[Dict]:
        keyword = job['keyword']
        location = job['location']
        log.info(f"Searching: {keyword} in {location}")
        results = self.scraper.search(keyword, location, num_results=10)
        return [{
            'title': r['title'],
            'description': r['description'],
            'url': r['url'],
            'post_text': r['description'],
        } for r in results]

    def submit_results(self, job_id: int, results: List[Dict]):
        url = f"{self.master_url}/api/jobs/{job_id}/submit"
        headers = {"X-Agent-Key": self.agent_key}
        try:
            response = requests.post(url, json={"results": results}, headers=headers, timeout=30)
            if response.status_code == 200:
                log.info(f"Submitted {len(results)} results")
                return True
        except Exception as e:
            log.error(f"Submit failed: {e}")
        return False

    def run(self, poll_interval: int = 60):
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
