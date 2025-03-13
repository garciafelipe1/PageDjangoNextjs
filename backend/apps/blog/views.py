from rest_framework.generics import ListAPIView,RetrieveAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound,APIException
from rest_framework import permissions
from .models import Post,Heading,PostAnalytics
from .serializers import PostSerializer,PostListSerializer,HeadingSerializer,PostView
from .utils import get_client_ip





class PostListView(APIView):
    def get(self,request,*args,**kwargs):
        try:
            post=Post.objects.all()
            
            if not post.exists():
                raise NotFound(detail="No posts found")
            
            serializer_posts=PostListSerializer(post,many=True).data 
            
        except Post.DoesNotExist:
            raise NotFound(detail="No posts found")
        except Exception as e:
            raise APIException(detail=f"An unexpected error ocurred: {str(e)}")
        
        return Response(serializer_posts)
        
class PostDetailView(RetrieveAPIView):
    def get(self,request,slug):
        try:
            post=Post.postobjects.get(slug=slug)
        except Post.DoesNotExist:
            raise NotFound(detail="the requested post does not exist")
        except Exception as e:
            raise APIException(detail=f"An unexpected error ocurred: {str(e)}")
        serializer_post=PostSerializer(post).data
        
        #incrementa la vista
        try:
            post_analytics=PostAnalytics.objects.get(post=post)
            post_analytics.increment_views(request)
        except PostAnalytics.DoesNotExist:
           raise NotFound(detail="the requested post does not exist")
        except Exception as e:
            raise APIException(detail=f"An error ocurred while updating post analytics : {str(e)}")
        
        
        
        return Response (serializer_post)


class PostHeadingsView(ListAPIView):
    serializer_class=HeadingSerializer
    
    def get_queryset(self):
        post_slug=self.kwargs['slug']
        return Heading.objects.filter(post__slug=post_slug)



class IncrementPostView(APIView):
    # permission_classes=[perm]
    def post(self,request):
        
        
        data=request.data
        try:
            post=Post.postobjects.get(slug=data['slug'])
        except Post.DoesNotExist:
            raise NotFound(detail="the requested post does not exist")
             
        try:
            post_analytics, created = PostAnalytics.objects.get_or_create(post=post)
            post_analytics.increment_clicks()  # Correcto: sin argumentos adicionales
        except Exception as e:
            raise APIException(detail=f"An error ocurred while updating post analytics : {str(e)}")
        return Response({
            "message":"click incremeted successfuly",
            "clicks":post_analytics.clicks             
        })