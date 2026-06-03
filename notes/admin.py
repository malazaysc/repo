from django.contrib import admin

from .models import Attachment, Note, Tag


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("__str__", "owner", "source_type", "status", "created_at")
    list_filter = ("status", "source_type", "created_at")
    search_fields = ("title", "source_url", "cleaned_text", "summary")
    filter_horizontal = ("tags",)
    inlines = [AttachmentInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)
