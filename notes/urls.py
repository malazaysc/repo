from django.urls import path

from . import views

app_name = "notes"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("notes/add/", views.add_source, name="add_source"),
    path("notes/<int:pk>/", views.note_detail, name="detail"),
    path("notes/<int:pk>/status/", views.note_status, name="status"),
    path("notes/<int:pk>/edit/", views.note_edit, name="edit"),
    path("notes/<int:pk>/delete/", views.note_delete, name="delete"),
    path("notes/<int:pk>/retry/", views.note_retry, name="retry"),
]
