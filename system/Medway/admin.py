from django.contrib import admin, messages
from django import forms
from django.shortcuts import render
from django.http import HttpResponse
from django.utils.timezone import now
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from .models import (
    Route,
    Drivers,
    Supplier,
    Representative,
    Monthly_sales,
    Product,
    Store,
    StoreProduct,
    Vehicle,
    jobs,
    Sale,
    SaleItem,
    Expenses,
)

from .forms import ProductAdminForm


# --------------------------------------------------
# BASIC REGISTRATIONS
# --------------------------------------------------
admin.site.register(Route)
admin.site.register(Drivers)
admin.site.register(Supplier)


# --------------------------------------------------
# INLINE MODELS
# --------------------------------------------------
class StoreProductInline(admin.TabularInline):
    model = StoreProduct
    extra = 1
    fields = ("product", "quantity")
    autocomplete_fields = []


class MonthlySalesInline(admin.TabularInline):
    model = Monthly_sales
    extra = 0


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ("job", "amount", "description")


# --------------------------------------------------
# REPRESENTATIVE ADMIN
# --------------------------------------------------
@admin.register(Representative)
class RepresentativeAdmin(admin.ModelAdmin):
    inlines = [MonthlySalesInline]


# --------------------------------------------------
# STORE ADMIN
# --------------------------------------------------

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
list_display = ("name",)
inlines = [StoreProductInline]


# --------------------------------------------------
# PRODUCT ADMIN (ONLY ONE — IMPORTANT)
# --------------------------------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ("Name", "Supplier")
    search_fields = ("Name",)


# --------------------------------------------------
# VEHICLE ADMIN
# --------------------------------------------------
@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    inlines = [StoreProductInline]

    def save_related(self, request, form, formsets, change):
        for formset in formsets:
            instances = formset.save(commit=False)
            for obj in instances:
                main_store = Store.objects.filter(name__icontains="main").first()
                if main_store:
                    main_stock = StoreProduct.objects.filter(
                        store=main_store, product=obj.product
                    ).first()

                    if main_stock and main_stock.quantity < obj.quantity:
                        messages.error(
                            request,
                            f"❌ Not enough stock in Main Store for {obj.product.Name}"
                        )
                        return

                    if main_stock:
                        main_stock.quantity -= obj.quantity
                        main_stock.save()

                obj.save()

        super().save_related(request, form, formsets, change)


# --------------------------------------------------
# JOBS FORM
# --------------------------------------------------
class JobsForm(forms.ModelForm):
    class Meta:
        model = jobs
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        rep = cleaned_data.get("rep")
        driver = cleaned_data.get("driver")
        vehicle = cleaned_data.get("Vehicle")

        qs = jobs.objects.exclude(id=self.instance.id)

        if qs.filter(rep=rep).exists():
            raise forms.ValidationError(f"❌ Rep {rep} already assigned")

        if qs.filter(driver=driver).exists():
            raise forms.ValidationError(f"❌ Driver {driver} already assigned")

        if qs.filter(Vehicle=vehicle).exists():
            raise forms.ValidationError(f"❌ Vehicle {vehicle} already assigned")

        return cleaned_data


# --------------------------------------------------
# JOBS ADMIN
# --------------------------------------------------
@admin.register(jobs)
class JobsAdmin(admin.ModelAdmin):
    form = JobsForm
    readonly_fields = ("sale",)
    exclude = ("cos", "profit")

    def delete_view(self, request, object_id, extra_context=None):
        obj = self.get_object(request, object_id)

        if request.method == "POST":
            expenses = []

            for key, value in request.POST.items():
                if key.startswith("expense_name_"):
                    idx = key.split("_")[-1]
                    amount = request.POST.get(f"expense_amount_{idx}")
                    if value and amount:
                        expenses.append((value, float(amount)))

            for name, amount in expenses:
                Expenses.objects.create(name=name, amount=amount, job=obj)

            rep = obj.rep
            if rep:
                rep.Sales += obj.sale
                rep.save()

            month = obj.Date.strftime("%Y-%m")
            Monthly_sales.objects.update_or_create(
                Rep=rep,
                month=month,
                defaults={"sales": obj.sale},
            )

            sale, _ = Sale.objects.get_or_create(
                Date=now().date(),
                defaults={"total_sales": 0},
            )

            SaleItem.objects.create(
                sale=sale,
                job=obj,
                amount=obj.sale,
                description=f"{obj.rep} | {obj.route}",
            )

            sale.total_sales += obj.sale
            sale.save()

            self._return_vehicle_stock(obj)

            response = self._generate_pdf(obj, expenses)
            obj.delete()
            return response

        return render(
            request,
            "admin/custom_delete_form.html",
            {"object": obj},
        )

    def _return_vehicle_stock(self, job):
        main_store = Store.objects.filter(name__icontains="main").first()
        if not main_store:
            return

        stocks = StoreProduct.objects.filter(vehical=job.Vehicle)
        for s in stocks:
            main_stock, _ = StoreProduct.objects.get_or_create(
                store=main_store, product=s.product, defaults={"quantity": 0}
            )
            main_stock.quantity += s.quantity
            main_stock.save()
            s.delete()

    def _generate_pdf(self, job, expenses):
        filename = f"Job_Report_{job.id}.pdf"
        c = canvas.Canvas(filename, pagesize=A4)

        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, 800, f"JOB REPORT #{job.id}")

        y = 760
        c.setFont("Helvetica", 12)
        c.drawString(50, y, f"Rep: {job.rep}")
        c.drawString(50, y - 20, f"Vehicle: {job.Vehicle}")
        c.drawString(50, y - 40, f"Sale: Rs {job.sale}")

        c.save()

        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="{filename}"'
            return response


# --------------------------------------------------
# ADMIN TITLES
# --------------------------------------------------
admin.site.site_header = "Medway Marketing Administration"
admin.site.site_title = "Medway Marketing Admin"
admin.site.index_title = "Welcome to Medway Marketing Admin Panel"
