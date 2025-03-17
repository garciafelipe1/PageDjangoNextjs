from rest_framework_api.views import StandardAPIView
from rest_framework.exceptions import NotFound,APIException
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
import redis
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from .models import Post,Heading,PostAnalytics,Category,CategoryAnalytics
from .serializers import PostSerializer,PostListSerializer,HeadingSerializer,CategoryListSerializer
from .utils import get_client_ip
from .tasks import increment_post_views_task
from django.db.models import Prefetch
from faker import Faker
import random
import uuid
from django.utils.text import slugify
from rest_framework.pagination import PageNumberPagination

redis_client=redis.Redis(host=settings.REDIS_HOST,port=6379,db=0)

class PostPagination(PageNumberPagination):
    page_size = 10  
    page_size_query_param = 'page_size'
    max_page_size = 50  


class PostListView(APIView):

    def get(self, request, *args, **kwargs):
        try:
            search = request.query_params.get("search", "").strip()
            sort = request.query_params.get("sort", "created_at")
            sort_order = request.query_params.get("order", "desc")
            categories = request.query_params.getlist("category", [])
            page = request.query_params.get('page', '1')

            # Validar que la página es un número válido
            try:
                page = int(page)
            except ValueError:
                return Response({"detail": "Invalid page number"}, status=400)

            valid_sort_fields = {"title", "created_at"}
            if sort not in valid_sort_fields:
                sort = "created_at"

            sort = f"-{sort}" if sort_order == "desc" else sort

            cache_key = f"post_list:{search}:{sort}:{','.join(categories)}:page_{page}"
            cached_data = cache.get(cache_key)

            # Si hay datos en caché, devolver toda la respuesta (incluyendo paginación)
            if cached_data:
                return Response(cached_data, status=200)

            posts = Post.postobjects.all()

            if search:
                posts = posts.filter(Q(title__icontains=search) | Q(description__icontains=search))

            if categories:
                posts = posts.filter(category__name__in=categories).distinct()

            posts = posts.order_by(sort)

            if not posts.exists():
                raise NotFound(detail="No posts found")

            # Aplicar paginación
            paginator = PostPagination()
            paginated_posts = paginator.paginate_queryset(posts, request, view=self)

            if paginated_posts is None:
                raise NotFound(detail="Pagination error")

            # Serializar los datos
            serializer_posts = PostListSerializer(paginated_posts, many=True).data

            # Obtener la respuesta paginada
            paginated_response = paginator.get_paginated_response(serializer_posts)

            # Guardar la respuesta completa en caché
            cache.set(cache_key, paginated_response.data, timeout=60 * 5)

            return paginated_response

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
        return Response(serializer_data)
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

class CategoryListView(StandardAPIView):
    def get(self, request):

        try:
            # Parametros de solicitud
            parent_slug = request.query_params.get("parent_slug", None)
            ordering = request.query_params.get("ordering", None)
            sorting = request.query_params.get("sorting", None)
            search = request.query_params.get("search", "").strip()
            page = request.query_params.get("p", "1")

            # Construir clave de cache para resultados paginados
            cache_key = f"category_list:{page}:{ordering}:{sorting}:{search}:{parent_slug}"
            cached_categories = cache.get(cache_key)
            if cached_categories:
                # Serializar los datos del caché
                serialized_categories = CategoryListSerializer(cached_categories, many=True).data
                # Incrementar impresiones en Redis para los posts del caché
                for category in cached_categories:
                    redis_client.incr(f"category:impressions:{category.id}")  # Usar `post.id`
                return self.paginate(request, serialized_categories)

            # Consulta inicial optimizada
            if parent_slug:
                categories = Category.objects.filter(parent__slug=parent_slug).prefetch_related(
                    Prefetch("category_analytics", to_attr="analytics_cache")
                )
            else:
                # Si no especificamos un parent_slug buscamos las categorias padre
                categories = Category.objects.filter(parent__isnull=True).prefetch_related(
                    Prefetch("category_analytics", to_attr="analytics_cache")
                )

            if not categories.exists():
                raise NotFound(detail="No categories found.")
            
            # Filtrar por busqueda
            if search != "":
                categories = categories.filter(
                    Q(name__icontains=search) |
                    Q(slug__icontains=search) |
                    Q(title__icontains=search) |
                    Q(description__icontains=search)
                )
            
            # Ordenamiento
            if sorting:
                if sorting == 'newest':
                    categories = categories.order_by("-created_at")
                elif sorting == 'recently_updated':
                    categories = categories.order_by("-updated_at")
                elif sorting == 'most_viewed':
                    categories = categories.annotate(popularity=F("analytics_cache__views")).order_by("-popularity")

            if ordering:
                if ordering == 'az':
                    posts = posts.order_by("name")
                if ordering == 'za':
                    posts = posts.order_by("-name")

            # Guardar los objetos en el caché
            cache.set(cache_key, categories, timeout=60 * 5)

            # Serializacion
            serialized_categories = CategoryListSerializer(categories, many=True).data

            # Incrementar impresiones en Redis
            for category in categories:
                redis_client.incr(f"category:impressions:{category.id}")

            return self.paginate(request, serialized_categories)
        except Exception as e:
                raise APIException(detail=f"An unexpected error occurred: {str(e)}")
           
           
class CategoryDetailView(APIView):
    
    def get(self, request):

        try:
            # Obtener parametros
            slug = request.query_params.get("slug", None)
            page = request.query_params.get("p", "1")

            if not slug:
                return self.error("Missing slug parameter")
            
            # Construir cache
            cache_key = f"category_posts:{slug}:{page}"
            cached_posts = cache.get(cache_key)
            if cached_posts:
                # Serializar los datos del caché
                serialized_posts = PostListSerializer(cached_posts, many=True).data
                # Incrementar impresiones en Redis para los posts del caché
                for post in cached_posts:
                    redis_client.incr(f"post:impressions:{post.id}")  # Usar `post.id`
                return Response(serialized_posts)

            # Obtener la categoria por slug
            category = get_object_or_404(Category, slug=slug)

            # Obtener los posts que pertenecen a esta categoria
            posts = Post.postobjects.filter(category=category).select_related("category").prefetch_related(
                Prefetch("post_analytics", to_attr="analytics_cache")
            )
            
            if not posts.exists():
                raise NotFound(detail=f"No posts found for category '{category.name}'")
            
            # Guardar los objetos en el caché
            cache.set(cache_key, posts, timeout=60 * 5)

            # Serializar los posts
            serialized_posts = PostListSerializer(posts, many=True).data

            # Incrementar impresiones en Redis
            for post in posts:
                redis_client.incr(f"post:impressions:{post.id}")

            return Response( serialized_posts)
        except Exception as e:
            raise APIException(detail=f"An unexpected error occurred: {str(e)}")         
           
           
                     
class IncrementCategoryClicksView(APIView):
    
    def post(self,request):
        
        
        data=request.data
        try:
            category=Category.objects.get(slug=data['slug'])
        except Category.DoesNotExist:
            raise NotFound(detail="the requested post does not exist")
             
        try:
            category_analytics, created = CategoryAnalytics.objects.get_or_create(category  =category)
            category_analytics.increment_clicks()  # Correcto: sin argumentos adicionales
        except Exception as e:
            raise APIException(detail=f"An error ocurred while updating post analytics : {str(e)}")
        return self.response({
            "message":"click incremeted successfuly",
            "clicks":category_analytics.clicks             
        })           
           
           
           
class GenerateFakePostView(StandardAPIView):
    
    def get(self,request):
        fake = Faker()
        
        categories = list(Category.objects.all())
        
        if not categories:
            return self.response("No categories found",400)
        
        posts_to_generate=100
        status_options = ["draft", "published"]
        
        for _ in range(posts_to_generate):
            title = fake.sentence(nb_words=6)
            post = Post(
                id=uuid.uuid4(),
                title = title,
                description= fake.sentence(nb_words=12),
                content=fake.paragraph(nb_sentences=5),
                keywords=", ".join(fake.words(nb=5)),
                slug = slugify(title),
                category=random.choice(categories),
                status=random.choice(status_options),
            )
            post.save()
            
        return self.response(f"{posts_to_generate} post generados correctamente")
    
class GenerateFakeAnalyticsView(StandardAPIView):
    
    def get(self,request):
        
        fake=Faker()
        
        
        posts = Post.objects.all()
        
        if not posts:
            return self.response({"error":"No posts found"},status=400)
        
        analytics_to_generate=len(posts)
        
        for post in posts:
            views=random.randint(50,1000)
            impressions = views + random.randint(100,2000)
            clicks=random.randint(0, views)
            avg_time_on_page=round(random.uniform(10,300),2)
            
            
            analytics, created=PostAnalytics.objects.get_or_create(post=post)
            analytics.views=views
            analytics.impressions = impressions
            analytics.clicks = clicks
            analytics.avg_time_on_page = avg_time_on_page
            analytics._update_click_through_rate()
            analytics.save()
            
        return self.response({"message":f"analiticas generadas para {analytics_to_generate} posts"}) 