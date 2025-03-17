from celery  import shared_task
import redis
import logging

from .models import PostAnalytics,Post,CategoryAnalytics,Category
from django.conf import settings
logger = logging.getLogger(__name__)

redis_client=redis.Redis(host=settings.REDIS_HOST,port=6379,db=0)


@shared_task
def increment_post_impressions(post_id):
    try:
        analytics,created=PostAnalytics.objects.get_or_create(post__id=post_id)
        analytics.increment_impressions()
    except Exception as e:
        logger.warning(f"error incrementing impressions for post ID {post_id}:{str(e)}")


@shared_task
def increment_post_views_task(slug, ip_address):
    try:
        post = Post.objects.get(slug=slug)
        post_analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        post_analytics.increment_view(ip_address)
    except Exception as e:
        logger.info(f"error incrementing views for post slug {slug}:{str(e)}")


@shared_task
def sync_impressions_to_db():
    """
    Sincronizar las impresiones almacenadas en redis con la base de datos
    """
    keys = redis_client.keys("post:impressions:*")
    for key in keys:
        try:
            post_id = key.decode("utf-8").split(":")[-1]

            # Validar que el post existe
            try:
                post = Post.objects.get(id=post_id)
            except Post.DoesNotExist:
                logger.info(f"Post with ID {post_id} does not exist. Skipping.")
                continue

            # Obtener impresiones de redis
            impressions = int(redis_client.get(key))
            if impressions == 0:
                redis_client.delete(key)
                continue
            
            # Obtener y crear instancia de category analytics
            analytics, created = PostAnalytics.objects.get_or_create(post=post)

            # Incrementar impresiones
            analytics.impressions += impressions
            analytics.save()

            # Incrementar la tasa de clics (CTR)
            analytics._update_click_through_rate()

            # Eliminar la clave de redis despues de sincronizar
            redis_client.delete(key)
        except Exception as e:
            print(f"Error syncing impressions for {key}: {str(e)}")


@shared_task
def sync_category_impressions_to_db():
    """
    Sincronizar las impresiones almacenadas en redis con la base de datos
    """
    keys = redis_client.keys("category:impressions:*")
    for key in keys:
        try:
            # Decodificar y extraer el ID de la categoría desde la clave Redis
            category_id = key.decode("utf-8").split(":")[-1]

            # Validar que la categoria existe
            try:
                category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                logger.info(f"Category with ID {category_id} does not exist. Skipping.")
                continue
            
            # Obtener impresiones de redis
            impressions = int(redis_client.get(key))
            if impressions == 0:
                redis_client.delete(key)
                continue

            # Obtener y crear instancia de category analytics
            analytics, created = CategoryAnalytics.objects.get_or_create(category=category)

            # Incrementar impresiones
            analytics.impressions += impressions
            analytics.save()

            # Actualizar tasa de clics (CTR)
            analytics._update_click_through_rate()

            # Eliminar la clave de redis despues de sincronizar
            redis_client.delete(key)
        except Exception as e:
            print(f"Error syncing impressions for {key}: {str(e)}")

        
        