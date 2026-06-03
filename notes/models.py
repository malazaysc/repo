from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class SourceType(models.TextChoices):
    YOUTUBE = "youtube", "YouTube"
    ARTICLE = "article", "Article / Link"
    X = "x", "X / Twitter"
    TEXT = "text", "Text"
    IMAGE = "image", "Image"


class NoteStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"


class Tag(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Note(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    title = models.CharField(max_length=500, blank=True)
    source_url = models.URLField(max_length=2000, blank=True)
    source_type = models.CharField(
        max_length=20, choices=SourceType.choices, default=SourceType.ARTICLE
    )
    status = models.CharField(
        max_length=20, choices=NoteStatus.choices, default=NoteStatus.PENDING
    )

    # Extracted content
    raw_content = models.TextField(blank=True)
    cleaned_text = models.TextField(blank=True)

    # AI-generated
    summary = models.TextField(blank=True)
    highlights = models.JSONField(default=list, blank=True)

    # Source-specific metadata (author, duration, published date, thumbnail, ...)
    metadata = models.JSONField(default=dict, blank=True)

    tags = models.ManyToManyField(Tag, related_name="notes", blank=True)

    error_message = models.TextField(blank=True)

    # Postgres full-text search vector (title/summary/content), updated on ingest
    # and edit. GIN-indexed for fast `@@` queries.
    search_vector = SearchVectorField(null=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "-created_at"]),
            models.Index(fields=["status"]),
            GinIndex(fields=["search_vector"], name="note_search_gin"),
        ]

    def __str__(self):
        return self.title or self.source_url or f"Note #{self.pk}"

    def get_absolute_url(self):
        return reverse("notes:detail", args=[self.pk])

    @property
    def is_in_progress(self):
        return self.status in {NoteStatus.PENDING, NoteStatus.PROCESSING}

    def mark_processing(self):
        self.status = NoteStatus.PROCESSING
        self.save(update_fields=["status", "updated_at"])

    def mark_failed(self, message: str):
        self.status = NoteStatus.FAILED
        self.error_message = message[:5000]
        self.save(update_fields=["status", "error_message", "updated_at"])

    def update_search_vector(self):
        """Recompute the weighted FTS vector from the row's current content."""
        Note.objects.filter(pk=self.pk).update(
            search_vector=(
                SearchVector("title", weight="A")
                + SearchVector("summary", weight="B")
                + SearchVector("cleaned_text", weight="C")
            )
        )


class Attachment(models.Model):
    class Kind(models.TextChoices):
        IMAGE = "image", "Image"
        FILE = "file", "File"

    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="attachments")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.IMAGE)
    file = models.FileField(upload_to="attachments/%Y/%m/", blank=True, null=True)
    remote_url = models.URLField(max_length=2000, blank=True)
    caption = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.caption or self.remote_url or f"Attachment #{self.pk}"
