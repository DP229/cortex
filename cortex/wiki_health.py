"""
Cortex Wiki Health - Automated wiki maintenance and linting

Checks for:
- Broken links (references to non-existent articles)
- Orphaned articles (no backlinks)
- Stale content (not updated in X days)
- Empty articles (very little content)
- Duplicate/similar articles (high overlap)
- Suggests new articles (mentioned but undocumented concepts)

Usage:
    checker = WikiHealthChecker(knowledgebase)
    issues = checker.check_all()
    suggestions = checker.suggest_new_articles()
"""

import os
import re
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging

from cortex.knowledgebase import KnowledgeBase

logger = logging.getLogger(__name__)


@dataclass
class HealthIssue:
    """A wiki health issue"""
    type: str  # "broken_link", "orphaned", "stale", "empty", "duplicate"
    severity: str  # "error", "warning", "info"
    article: str
    message: str
    suggestion: str = ""


class WikiHealthChecker:
    """Check wiki health and suggest improvements."""
    
    def __init__(self, knowledgebase: KnowledgeBase):
        self.kb = knowledgebase
    
    def check_all(self) -> List[HealthIssue]:
        """Run all health checks"""
        issues = []
        issues.extend(self.check_broken_links())
        issues.extend(self.check_orphaned_articles())
        issues.extend(self.check_stale_articles())
        issues.extend(self.check_empty_articles())
        issues.extend(self.check_suggest_merges())
        return issues
    
    def check_broken_links(self) -> List[HealthIssue]:
        """Find links to non-existent articles"""
        issues = []
        
        for article in self.kb.list_articles():
            links = self.kb._extract_links(article.content)
            for link in links:
                target = self.kb.get_article(link)
                if not target:
                    issues.append(HealthIssue(
                        type="broken_link",
                        severity="error",
                        article=article.path,
                        message=f"Broken link to: {link}",
                        suggestion=f"Create the article or remove the link",
                    ))
        
        return issues
    
    def check_orphaned_articles(self) -> List[HealthIssue]:
        """Find articles with no backlinks"""
        issues = []
        
        for article in self.kb.list_articles():
            if article.path == "index.md":
                continue
            backlinks = self.kb.get_backlinks(article.path)
            if not backlinks:
                issues.append(HealthIssue(
                    type="orphaned",
                    severity="warning",
                    article=article.path,
                    message="No articles link to this article",
                    suggestion="Add links from related articles",
                ))
        
        return issues
    
    def check_stale_articles(self, days: int = 30) -> List[HealthIssue]:
        """Find articles not updated recently"""
        issues = []
        cutoff = time.time() - (days * 24 * 60 * 60)
        
        for article in self.kb.list_articles():
            if article.updated_at < cutoff:
                issues.append(HealthIssue(
                    type="stale",
                    severity="info",
                    article=article.path,
                    message=f"Article not updated in {days} days",
                    suggestion="Review and update with latest information",
                ))
        
        return issues
    
    def check_empty_articles(self) -> List[HealthIssue]:
        """Find articles with very little content"""
        issues = []
        
        for article in self.kb.list_articles():
            if article.word_count < 50:
                issues.append(HealthIssue(
                    type="empty",
                    severity="warning",
                    article=article.path,
                    message=f"Article has only {article.word_count} words",
                    suggestion="Expand the article or merge with related content",
                ))
        
        return issues
    
    def check_suggest_merges(self) -> List[HealthIssue]:
        """Suggest articles that should be merged"""
        issues = []
        articles = self.kb.list_articles()
        
        for i, a1 in enumerate(articles):
            for a2 in articles[i+1:]:
                # Simple similarity check
                words1 = set(a1.content.lower().split())
                words2 = set(a2.content.lower().split())
                
                if len(words1) > 0 and len(words2) > 0:
                    overlap = len(words1 & words2)
                    similarity = overlap / min(len(words1), len(words2))
                    
                    if similarity > 0.7 and a1.word_count < 500 and a2.word_count < 500:
                        issues.append(HealthIssue(
                            type="duplicate",
                            severity="info",
                            article=f"{a1.path}, {a2.path}",
                            message=f"Articles are {similarity:.0%} similar",
                            suggestion="Consider merging these articles",
                        ))
        
        return issues
    
    def suggest_new_articles(self, agent=None) -> List[str]:
        """Suggest new articles to write based on mentioned but undocumented concepts"""
        suggestions = []
        
        # Find mentioned but undocumented concepts
        all_content = ""
        for article in self.kb.list_articles():
            all_content += article.content + "\n"
        
        # Common words to exclude from suggestions
        common_words = {
            "Related", "See", "Also", "Key", "Concepts", "Introduction",
            "Summary", "Conclusion", "References", "Notes", "Example",
            "Examples", "Overview", "Background", "Details", "More",
            "Content", "Section", "Chapter", "Part", "Table", "Figure",
        }
        
        # Find potential concepts (capitalized phrases, technical terms)
        # Use [ ]+ instead of \s+ to avoid matching across newlines
        potential_concepts = set()
        for match in re.finditer(r'\b([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b', all_content):
            term = match.group(1)
            if len(term) > 3 and term not in common_words and '\n' not in term:
                potential_concepts.add(term)
        
        # Check which ones don't have articles
        existing_titles = {a.title.lower() for a in self.kb.list_articles()}
        
        for concept in potential_concepts:
            if concept.lower() not in existing_titles:
                # Check if it's mentioned multiple times (important concept)
                count = all_content.lower().count(concept.lower())
                if count >= 3:
                    suggestions.append(concept)
        
        return suggestions[:20]
    
    def get_summary(self) -> Dict:
        """Get a summary of wiki health"""
        issues = self.check_all()
        
        by_severity = {"error": 0, "warning": 0, "info": 0}
        by_type = {}
        
        for issue in issues:
            by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1
            by_type[issue.type] = by_type.get(issue.type, 0) + 1
        
        return {
            "total_issues": len(issues),
            "by_severity": by_severity,
            "by_type": by_type,
            "suggestions_count": len(self.suggest_new_articles()),
        }
