from django.shortcuts import render
from django.template import loader
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate, login
from .models import jobs, Representative, Product, Vehicle, StoreProduct, SaleItem
from django.db.models import F
from django.contrib import messages
from django.http import HttpResponseRedirect
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from django.utils.timezone import now
from django.contrib.auth.hashers import check_password

def login_user(request):
    if request.method == 'POST':
        password = request.POST.get('Password')
        NIC = request.POST.get('NIC')

        try:
            # 1️⃣ Get representative by NIC
            rep = Representative.objects.get(Nic=NIC)

            # 2️⃣ Check hashed password
            if not check_password(password, rep.password):
                messages.error(request, 'Invalid NIC or password')
                return redirect('home')

            # 3️⃣ Find ongoing job for this rep
            job = jobs.objects.filter(rep=rep).first()

            if not job:
                messages.error(request, 'No ongoing jobs')
                return redirect('login_user')

            # 4️⃣ Save session
            request.session['NIC'] = rep.Nic
            request.session['vehicle_id'] = job.Vehicle.id

            messages.success(request, 'You successfully logged in.')
            return redirect('rep_view')

        except Representative.DoesNotExist:
            messages.error(request, 'Invalid NIC or password')

    return render(request, 'home.html')


def rep_view(request):
    vehicle_id = request.session.get("vehicle_id")
    vehicle = Vehicle.objects.get(id=vehicle_id)

    # Prepare stock list for template
    vehicle_stocks = StoreProduct.objects.filter(vehical=vehicle)
    stocks = {
        Product.objects.get(id=s["product_id"]): s["quantity"]
        for s in vehicle_stocks.values()
    }

    if request.method == "POST":
        data = dict(request.POST.items())

        customer = data.pop("Customer", "Unknown")
        discount = data.pop("Discount", "").strip()

        filename = f"media/bills/Bill_{customer}.pdf"
        c = canvas.Canvas(filename, pagesize=A4)

        # ===== HEADER =====
        c.setFillColor(HexColor("#ff8c00"))
        # Orange header 
        c.setFont("Courier-Bold", 34) 
        c.drawString(240, 800, "Medway Marketing")

        #address 
        c.setFillColor(HexColor("#000000"))
        c.setFont("Helvetica-Bold", 12) 
        c.drawString(380, 776, "200/2, Negombo Rd, Nittambuwa") 
        c.drawString(480, 758, "Tel:0772153208") 
        #br number 
        c.setFont("Helvetica-Bold", 10) 
        c.drawString(40, 805, "Per. No.:5156") 
        c.drawString(40, 785,"W/ATH/L/13268")

        c.setFont("Helvetica-Bold", 18)
        c.drawString(40, 700, f"Customer: {customer}")

        # ===== TABLE HEADERS =====
        c.setFont("Helvetica-Bold", 15)
        c.drawString(40, 650, "QTY")
        c.drawString(100, 650, "Product")
        c.drawString(350, 650, "Rate")
        c.drawString(470, 650, "Amount")
        c.line(40, 640, 540, 640)

        y = 610
        total = 0

        for key, value in data.items():
            if key == "csrfmiddlewaretoken":
                continue

            try:
                qty = int(value)
                if qty <= 0:
                    continue
            except (ValueError, TypeError):
                continue

            try:
                product = Product.objects.get(Name=key)
                vehicle_stock = StoreProduct.objects.filter(
                    vehical=vehicle, product=product
                ).first()
                print(key)
                job = jobs.objects.filter(Vehicle=vehicle).first()

                if not vehicle_stock:
                    messages.error(request, f"No stock for {product.Name}")
                    return redirect('rep_view')

                if vehicle_stock.quantity < qty:
                    messages.error(
                        request,
                        f"Not enough stock for {product.Name}. Available: {vehicle_stock.quantity}"
                    )
                    return redirect('rep_view')

                retail_price = int(product.Retail_price)
                # ===== PRICE LOGIC =====
                if discount:
                    #price for the shop
                    print(discount)
                    shop_price = retail_price - retail_price*((int(int(discount))) / 100)
                    print(shop_price)
                    price = int(product.Retail_price)
                    job.cos += int(product.cost)*int(value)
                    job.profit += int(shop_price - int(product.cost))*int(value)
                    job.save() 
                else:
                    price = int(product.Selling_price)
                    job.cos += int(product.cost)*int(value)
                    job.profit += int(price - int(product.cost))*int(value)
                    job.save()

                amount = int(price * qty)
                total += amount

                # ===== PDF ROW =====
                c.setFont("Helvetica", 14)
                c.drawString(40, y, str(qty))
                c.drawString(100, y, product.Name)
                c.drawString(350, y, str(int(price)))
                c.drawRightString(520, y, str(amount))
                y -= 30

                # ===== UPDATE DB =====
                vehicle_stock.quantity -= qty

                vehicle_stock.save()

            except Product.DoesNotExist:
                messages.error(request, f"Product '{key}' not found")

        if discount:
            job.sale += total - total*((int(discount)) / 100)
            job.save() 
        else:
            job.sale += total
            job.save()

        # ===== TOTAL =====
        c.line(40, y, 540, y)
        y -= 30
        c.setFont("Helvetica-Bold", 16)
        c.drawRightString(138, y, f"Grand Total:")
        c.drawRightString(520, y, f"{total}")

        if discount:
            c.drawRightString(153, y-30, f"Discount {discount}%:") 
            c.drawRightString(520, y-30, f"- {total*((int(discount)) / 100)}")
            c.drawRightString(87, y-60, f"Total:")
            c.drawRightString(520, y-60, f" {total - total*((int(discount)) / 100)}")
        else:
            c.drawRightString(520, y, f"Grand Total: {total}")

        c.save()

        with open(filename, "rb") as pdf:
            response = HttpResponse(pdf.read(), content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="Bill_{customer}.pdf"'
            return response

    # ✅ THIS LINE FIXES YOUR ERROR
    return render(request, "rep_view.html", {"stock": stocks.items()})

