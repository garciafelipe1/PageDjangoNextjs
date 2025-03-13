
from django.urls import path
from .views import(
    PostListView,
    PostDetailView,
    IncrementPostView,
    PostHeadingsView
    ) 

urlpatterns = [
    path('posts/', PostListView.as_view(), name="post-list"),
    path('post/<slug>/', PostDetailView.as_view(), name="post-detail"),
    path('posts/increment_clicks/', IncrementPostView.as_view(), name="increment-post-click"),
    path('post/<slug>/headings/', PostHeadingsView.as_view(), name="post-headings"),
    
    
]