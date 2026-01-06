from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.hashers import make_password, check_password
from django.db.models import F, Sum
from django.db.models.functions import Coalesce
from decimal import Decimal
from django.db.models import F, Sum, DecimalField
from django.db.models.functions import Cast, Coalesce
from decimal import Decimal

class Representative(models.Model):
    Name = models.CharField(max_length=100)
    Nic = models.CharField(max_length=12, unique=True)
    Phone = models.CharField(max_length=10)
    Address = models.CharField(max_length=255)
    password = models.CharField(max_length=128)  # store hashed password
    Sales = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        # Hash the password automatically if it's not hashed yet
        if self.password and not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def check_password(self, raw_password):
        """Verify a raw password against the hashed password"""
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.Name}{'\u00A0\u00A0\u00A0'}{'\u00A0\u00A0\u00A0'}{self.Nic}"

# record monthly sales of reps
class Monthly_sales(models.Model):
	Rep = models.ForeignKey(Representative, on_delete=models.CASCADE)
	month = models.CharField(max_length=255)
	sales = models.IntegerField(default=0)

	def __str__(self):
	    # Convert date to string and remove last three characters
	    return str(self.month)[:-3]

class Supplier(models.Model):
    name = models.CharField(max_length=255, unique=True)
    contact_info = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Product(models.Model):
	Name = models.CharField(max_length=500)
	Barcode_no = models.CharField(max_length=20)
	cost = models.CharField(max_length=7)
	Supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
	Selling_price = models.CharField(max_length=7)
	Retail_price = models.CharField(max_length=7)

	def __str__(self):
		return f"{self.Name}"

class Route(models.Model):
	Name = models.CharField(max_length=500)
	Route_no = models.CharField(max_length=20)

	def __str__(self):
		return f"{self.Name}{'\u00A0\u00A0\u00A0'}{'\u00A0\u00A0\u00A0'}{self.Route_no}"

class Vehicle(models.Model):
	Name = models.CharField(max_length=500)
	Vehical_no = models.CharField(max_length=20)

	def __str__(self):
		return f"{self.Name}{'\u00A0\u00A0\u00A0'}{'\u00A0\u00A0\u00A0'}{self.Vehical_no}"
	
	# 🔥 TOTAL SELLING VALUE IN VEHICLE
	def total_stock_value(self):
		total = StoreProduct.objects.filter(
			vehical=self
		).aggregate(
			total=Coalesce(
				Sum(
					F("quantity") *
					Cast(
						F("product__Selling_price"),
						output_field=DecimalField(max_digits=10, decimal_places=2)
					),
					output_field=DecimalField(max_digits=12, decimal_places=2)
				),
				Decimal("0")
			)
		)["total"]

		return total

	# 🔥 TOTAL COST IN VEHICLE
	def total_stock_cost(self):
		total = StoreProduct.objects.filter(
			vehical=self
		).aggregate(
			total=Coalesce(
				Sum(
					F("quantity") *
					Cast(
						F("product__cost"),
						output_field=DecimalField(max_digits=10, decimal_places=2)
					),
					output_field=DecimalField(max_digits=12, decimal_places=2)
				),
				Decimal("0")
			)
		)["total"]

		return total

	# 🔥 EXPECTED PROFIT IN VEHICLE
	def total_stock_profit(self):
		return self.total_stock_value() - self.total_stock_cost()


class Drivers(models.Model):
	Name = models.CharField(max_length=500)
	Nic = models.CharField(max_length=12)
	Phone = models.CharField(max_length=10)
	Address = models.CharField(max_length=500)

	def __str__(self):
		return f"{self.Name}{'\u00A0\u00A0\u00A0'}{'\u00A0\u00A0\u00A0'}{self.Nic}"

class jobs(models.Model):
	rep = models.ForeignKey(Representative, on_delete=models.CASCADE)
	driver = models.ForeignKey(Drivers, on_delete=models.CASCADE)
	Vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
	route = models.ForeignKey(Route, on_delete=models.CASCADE)
	sale = models.IntegerField(default=0)
	cos = models.IntegerField(default=0)
	profit = models.IntegerField(default=0)

	def __str__(self):
		return f"{self.Vehicle} {'\u00A0\u00A0\u00A0'} {self.rep} {'\u00A0\u00A0\u00A0'} {self.driver}"


class Store(models.Model):
	name = models.CharField(max_length=500)
	products = models.ManyToManyField(Product, through='StoreProduct')  # Many-to-Many with an intermediate model
	
	
	def total_stock_value(self):
		total = StoreProduct.objects.filter(
			store=self
		).aggregate(
			total=Coalesce(
				Sum(
					F("quantity") *
					Cast(
						F("product__Selling_price"),
						output_field=DecimalField(max_digits=10, decimal_places=2)
					),
					output_field=DecimalField(max_digits=12, decimal_places=2)
				),
				Decimal("0.00")
			)
		)["total"]

		return total

	def total_stock_cost(self):
		total = StoreProduct.objects.filter(
			store=self
		).aggregate(
			total=Coalesce(
				Sum(
					F("quantity") *
					Cast(
						F("product__cost"),
						output_field=DecimalField(max_digits=10, decimal_places=2)
					),
					output_field=DecimalField(max_digits=12, decimal_places=2)
				),
				Decimal("0.00")
			)
		)["total"]

		return total
	
	# 🔥 EXPECTED PROFIT IN VEHICLE
	def total_stock_profit(self):
		return self.total_stock_value() - self.total_stock_cost()

class StoreProduct(models.Model):  # This tracks the quantity of each product in a store
    store = models.ForeignKey(Store, null=True, blank=True, on_delete=models.CASCADE)
    vehical = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)

class Sale(models.Model):
	Date = models.DateField(auto_now_add=True)
	total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	#cost_of_sales = models.CharField(max_length=500)
	#expenses =models.CharField(max_length=500)

	def __str__(self):
		return f"{self.Date}"

class SaleItem(models.Model):
    sale = models.ForeignKey(
        Sale,
        related_name="items",
        on_delete=models.CASCADE
    )
    job = models.ForeignKey(
        "jobs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField()

    def __str__(self):
        return f"Report for {self.sale.Date} - {self.amount}"


class Expenses(models.Model):
    job = models.ForeignKey(jobs, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name
