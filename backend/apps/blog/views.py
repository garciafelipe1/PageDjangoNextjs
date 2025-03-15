from rest_framework_api.views import StandardAPIView
from rest_framework.exceptions import NotFound,APIException
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.db.models import Q
import redis
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Post,Heading,PostAnalytics,Category
from .serializers import PostSerializer,PostListSerializer,HeadingSerializer
from .utils import get_client_ip
from .tasks import increment_post_views_task

from faker import Faker
import random
import uuid
from django.utils.text import slugify


redis_client=redis.Redis(host=settings.REDIS_HOST,port=6379,db=0)

class PostListView(APIView):  # Usa APIView si StandardAPIView no es crucial
    
    def get(self, request, *args, **kwargs):
        try:
            search = request.query_params.get("search", "").strip()
            sort = request.query_params.get("sort", "created_at")  # Orden por defecto
            sort_order = request.query_params.get("order", "desc")  # 'asc' o 'desc'

            valid_sort_fields = {"title", "created_at"}
            if sort not in valid_sort_fields:
                sort = "created_at"

            sort = f"-{sort}" if sort_order == "desc" else sort

            print("Search term:", search)
            print("Sorting by:", sort)

            cache_key = f"post_list:{search}:{sort}"
            cached_posts_data = cache.get(cache_key)

            if cached_posts_data:
                for post_data in cached_posts_data:
                    try:
                        post_id = int(post_data["id"])
                        redis_client.incr(f"post:impressions:{post_id}")
                    except ValueError:
                        print(f"Error: No se pudo convertir '{post_data['id']}' a entero.")
                
                return Response(cached_posts_data, status=200)

            posts = Post.postobjects.all()
            if search:
                posts = posts.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search)
                )

            posts = posts.order_by(sort)

            if not posts.exists():
                raise NotFound(detail="No posts found")

            serializer_posts = PostListSerializer(posts, many=True).data

            cache.set(cache_key, serializer_posts, timeout=60 * 5)

            for post in posts:
                redis_client.incr(f"post:impressions:{post.id}")

            return Response(serializer_posts, status=200)

        except NotFound as nf:
            return Response({"detail": str(nf)}, status=404)
        except Exception as e:
            return Response({"detail": f"Internal server error: {str(e)}"}, status=500)
class PostDetailView(APIView):
    
    def get(self,request):
        
        ip_address=get_client_ip(request)
        
        slug=request.query_params.get("slug")
        
        try:
            cached_post = cache.get(f"post:{slug}")
            if cached_post:
                increment_post_views_task.delay(cached_post['slug'],ip_address)
                return Response(cached_post)
            
            
            post = Post.postobjects.get(slug=slug)
            serializer_post = PostSerializer(post).data
            
            cache.set(f"post_detail:{slug}",serializer_post, timeout=60 * 5)
            
            increment_post_views_task.delay(post.slug, ip_address)
            
        except Post.DoesNotExist:
            raise NotFound(detail="the requested post does not exist")
        except Exception as e:
            raise APIException(detail=f"An unexpected error ocurred: {str(e)}")
        
        return Response(serializer_post)


class PostHeadingsView(APIView):
    serializer_class=HeadingSerializer
    
    
    def get(self,request):
        post_slug=request.query_params.get("slug")
        heading_objects=Heading.objects.filter(post__slug=post_slug)
        serializer_data=HeadingSerializer(heading_objects,many=True).data
        return self.response(serializer_data)
    # def get_queryset(self):
    #     post_slug=self.kwargs['slug']
    #     return Heading.objects.filter(post__slug=post_slug)



class IncrementPostView(APIView):
    
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
        return self.response({
            "message":"click incremeted successfuly",
            "clicks":post_analytics.clicks             
        })
        

# class GenerateFakePostView(StandardAPIView):
    
#     def get(self,request):
#         fake = Faker()
        
#         categories = list(Category.objects.all())
        
#         if not categories:
#             return self.response("No categories found",400)
        
#         posts_to_generate=100
#         status_options = ["draft", "published"]
        
#         for _ in range(posts_to_generate):
#             title = fake.sentence(nb_words=6)
#             post = Post(
#                 id=uuid.uuid4(),
#                 title = title,
#                 description= fake.sentence(nb_words=12),
#                 content=fake.paragraph(nb_sentences=5),
#                 keywords=", ".join(fake.words(nb=5)),
#                 slug = slugify(title),
#                 category=random.choice(categories),
#                 status=random.choice(status_options),
#             )
#             post.save()
            
#         return self.response(f"{posts_to_generate} post generados correctamente")
    
# class GenerateFakeAnalyticsView(StandardAPIView):
    
#     def get(self,request):
        
#         fake=Faker()
        
        
#         posts = Post.objects.all()
        
#         if not posts:
#             return self.response({"error":"No posts found"},status=400)
        
#         analytics_to_generate=len(posts)
        
#         for post in posts:
#             views=random.randint(50,1000)
#             impressions = views + random.randint(100,2000)
#             clicks=random.randint(0, views)
#             avg_time_on_page=round(random.uniform(10,300),2)
            
            
#             analytics, created=PostAnalytics.objects.get_or_create(post=post)
#             analytics.views=views
#             analytics.impressions = impressions
#             analytics.clicks = clicks
#             analytics.avg_time_on_page = avg_time_on_page
#             analytics._update_click_through_rate()
#             analytics.save()
            
#         return self.response({"message":f"analiticas generadas para {analytics_to_generate} posts"}) 