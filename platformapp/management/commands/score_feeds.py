from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand

from platformapp.models import RSSFeed
from platformapp.services import fetch_and_score_feeds


class Command(BaseCommand):
    help = "Fetch active RSS feeds, store unseen articles, score them, and flag high-risk items."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--backend", default="classical", choices=["classical", "bilstm", "mini_transformer"])
        parser.add_argument("--max-entries-per-feed", type=int, default=25)
        parser.add_argument("--review-threshold", type=float, default=0.8)
        parser.add_argument(
            "--seed",
            action="store_true",
            help="Create a small starter feed list if no feeds exist.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["seed"] and not RSSFeed.objects.exists():
            RSSFeed.objects.bulk_create(
                [
                    RSSFeed(name="BBC World", url="https://feeds.bbci.co.uk/news/world/rss.xml"),
                    RSSFeed(name="Reuters Top News", url="https://www.reutersagency.com/feed/?best-topics=top-news"),
                ],
                ignore_conflicts=True,
            )
            self.stdout.write(self.style.SUCCESS("Seeded starter RSS feeds."))

        result = fetch_and_score_feeds(
            backend=options["backend"],
            max_entries_per_feed=options["max_entries_per_feed"],
            review_threshold=options["review_threshold"],
        )
        self.stdout.write(self.style.SUCCESS(json.dumps(result, sort_keys=True)))
