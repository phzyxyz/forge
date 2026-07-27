from __future__ import annotations

from django.db import models


class Item(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    notes = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=64, default="general", db_index=True)
    score = models.IntegerField(default=0, db_index=True)

    class Meta:
        db_table = "items"
