from rest_framework.generics import ListAPIView,RetrieveAPIView
from rest_framework.views import APIView
from rest_framework.response import Response


from .models import Post,Heading
from .serializers import PostSerializer,PostListSerializer,HeadingSerializer,PostView
from .utils import get_client_ip





class PostListView(APIView):
    def get(self,request,*args,**kwargs):
        post=Post.objects.all()
        serializer_posts=PostListSerializer(post,many=True).data 
        return Response(serializer_posts)
        
class PostDetailView(RetrieveAPIView):
    def get(self,request,slug):
        post=Post.postobjects.get(slug=slug)
        serializer_post=PostSerializer(post).data
        
        client_ip=get_client_ip(request)
        
        if PostView.objects.filter(post=post,ip_address=client_ip).exists():
            return Response(serializer_post)
        
        PostView.objects.create(post=post,ip_address=get_client_ip)
        
        return Response (serializer_post)


class PostHeadingsView(ListAPIView):
    serializer_class=HeadingSerializer
    
    def get_queryset(self):
        post_slug=self.kwargs['slug']
        return Heading.objects.filter(post__slug=post_slug)
