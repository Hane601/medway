from django.contrib.auth.admin import UserAdmin
from .models import Products
from .models import Route
from .models import Drivers, Vehicals,Supplier, Representative
from .models import Main_store
from .models import jobs
from django.contrib import admin

# Register your models here.

admin.site.register(Products)
admin.site.register(Route)
admin.site.register(Vehicals)
admin.site.register(Drivers)
admin.site.register(Supplier)
admin.site.register(Representative)

@admin.register(jobs)
class jobsAdmin(admin.ModelAdmin):
    '''extra = 0

    fieldsets = (
        (None, {
            'fields': ('rep', 'driver', 'Vehical', 'Route','store')
        }),
    )'''
