"""
Debug logging endpoint for remote client debugging.
Stores debug reports from clients (especially mobile devices) for analysis.
"""

from datetime import datetime
from typing import Dict, List, Optional
import json
from pathlib import Path

class DebugLogger:
    def __init__(self, log_dir: str = "debug_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.reports: List[Dict] = []
        
    def log_client_report(self, report: Dict) -> str:
        """Store a debug report from a client."""
        timestamp = datetime.now()
        report['server_timestamp'] = timestamp.isoformat()
        
        # Add to in-memory list
        self.reports.append(report)
        
        # Keep only last 100 reports in memory
        if len(self.reports) > 100:
            self.reports = self.reports[-100:]
        
        # Save to file
        filename = self.log_dir / f"debug_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        return str(filename)
    
    def get_recent_reports(self, limit: int = 20) -> List[Dict]:
        """Get the most recent debug reports."""
        return self.reports[-limit:]
    
    def get_ios_reports(self, limit: int = 20) -> List[Dict]:
        """Get debug reports from iOS devices only."""
        ios_reports = [
            r for r in self.reports 
            if r.get('debugInfo', {}).get('isIOS') == True
        ]
        return ios_reports[-limit:]
    
    def search_reports(self, error_message: str) -> List[Dict]:
        """Search reports by error message."""
        return [
            r for r in self.reports
            if error_message.lower() in str(r.get('error', '')).lower()
        ]

# Global instance
debug_logger = DebugLogger()
