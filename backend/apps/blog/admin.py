from django.contrib import admin
from .models import Category,Post,Heading


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "title", "slug")
    search_fields = ("name", "title", "description","slug")
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("parent",)
    ordering=("name",)


class HeadingInline(admin.TabularInline):
    model=Heading
    extra=1
    fields=('title','level','order','slug')
    prepopulated_fields={"slug":("title",)}
    ordering=('order',)



@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display=('title','status','category','created_at','update_at')
    search_fields=('title','description','content','keywords','slug')
    prepopulated_fields = {"slug": ("title",)}
    list_filter=('status','category','update_at')
    ordering=('-created_at',)
    readonly_fields=('id','created_at','update_at')
    fieldsets=(
        ('General Information',{
            'fields':(
                'title',
                'description',
                'content',
                'thumbnail',
                'keywords',
                'slug',
                'category',
            )
        }),
        ('Status & Date',{
            'fields':(
                'status',
                'created_at',
                'update_at',
            )
            
        })
    )
    inlines=[HeadingInline]


# @admin.register(Heading)
# class HeadingAdmin(admin.ModelAdmin):
#     list_display=('title','post','level','order')
#     search_fields=('title','post__title')
#     list_filter=('level','post')
#     ordering=('post','order')
#     prepopulated_fields=({"slug":("title",)})
    


