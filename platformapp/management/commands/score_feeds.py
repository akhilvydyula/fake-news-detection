from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand

from platformapp.models import RSSFeed
from platformapp.services import fetch_and_score_feeds


DEFAULT_FEEDS = [
    ("NYTimes World", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("NPR News", "https://www.npr.org/rss/rss.php?id=1001"),
    ("Guardian World", "https://www.theguardian.com/world/rss"),
    ("Sky News World", "https://feeds.skynews.com/feeds/rss/world.xml"),
]


class Command(BaseCommand):
    help = "Fetch active RSS feeds, store unseen articles, score them, and flag high-risk items."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--backend", default="classical", choices=["classical", "bilstm", "mini_transformer"])
        parser.add_argument("--max-entries-per-feed", type=int, default=25)
        parser.add_argument("--review-threshold", type=float, default=0.8)
        parser.add_argument(
            "--seed",
            action="store_true",
            help="Upsert reliable starter feeds before ingesting.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["seed"]:
            # Deactivate a previously seeded URL that commonly fails or returns non-standard XML.
            RSSFeed.objects.filter(name__in=["BBC World", "Reuters Top News"]).update(
                is_active=False,
                last_error="Deactivated default seed: use a reliable RSS endpoint instead.",
            )
            for name, url in DEFAULT_FEEDS:
                RSSFeed.objects.update_or_create(
                    url=url,
                    defaults={"name": name, "is_active": True, "last_error": ""},
                )
            self.stdout.write(self.style.SUCCESS("Seeded starter RSS feeds."))

        result = fetch_and_score_feeds(
            backend=options["backend"],
            max_entries_per_feed=options["max_entries_per_feed"],
            review_threshold=options["review_threshold"],
        )
        self.stdout.write(self.style.SUCCESS(json.dumps(result, sort_keys=True)))
