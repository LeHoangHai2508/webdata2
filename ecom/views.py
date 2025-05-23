import os
import time
from django.shortcuts import render,redirect,reverse
from django.contrib.staticfiles import finders
import requests
from . import forms,models
from django.http import HttpResponseRedirect,HttpResponse
from django.core.mail import send_mail
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required,user_passes_test
from django.contrib import messages
from django.conf import settings
from collections import defaultdict
from . import models
from django.db.models import Prefetch
from django.core.files.base import ContentFile
from django.shortcuts import render
from .forms import ProductCSVForm, TransactionCSVForm
from io import TextIOWrapper
from .models import Transaction, Orders, Product
import csv, ast
from ecom.mafia import find_maximal_itemsets, find_maximal_itemsets_and_rules, mafia


def home_view(request):
    products=models.Product.objects.all()
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        counter=product_ids.split('|')
        product_count_in_cart=len(set(counter))
    else:
        product_count_in_cart=0
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')
    return render(request,'ecom/index.html',{'products':products,'product_count_in_cart':product_count_in_cart})


#for showing login button for admin(by sumit)
def adminclick_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')
    return HttpResponseRedirect('adminlogin')


def customer_signup_view(request):
    userForm=forms.CustomerUserForm()
    customerForm=forms.CustomerForm()
    mydict={'userForm':userForm,'customerForm':customerForm}
    if request.method=='POST':
        userForm=forms.CustomerUserForm(request.POST)
        customerForm=forms.CustomerForm(request.POST,request.FILES)
        if userForm.is_valid() and customerForm.is_valid():
            user=userForm.save()
            user.set_password(user.password)
            user.save()
            customer=customerForm.save(commit=False)
            customer.user=user
            customer.save()
            my_customer_group = Group.objects.get_or_create(name='CUSTOMER')
            my_customer_group[0].user_set.add(user)
        return HttpResponseRedirect('customerlogin')
    return render(request,'ecom/customersignup.html',context=mydict)

#-----------for checking user iscustomer
def is_customer(user):
    return user.groups.filter(name='CUSTOMER').exists()



#---------AFTER ENTERING CREDENTIALS WE CHECK WHETHER USERNAME AND PASSWORD IS OF ADMIN,CUSTOMER
def afterlogin_view(request):
    if is_customer(request.user):
        return redirect('customer-home')
    else:
        return redirect('admin-dashboard')

#---------------------------------------------------------------------------------
#------------------------ ADMIN RELATED VIEWS START ------------------------------
#---------------------------------------------------------------------------------
@login_required(login_url='adminlogin')
def admin_dashboard_view(request):
    # for cards on dashboard
    customercount=models.Customer.objects.all().count()
    productcount=models.Product.objects.all().count()
    ordercount=models.Orders.objects.all().count()

    # for recent order tables
    orders=models.Orders.objects.all()
    ordered_products=[]
    ordered_bys=[]
    for order in orders:
        ordered_product=models.Product.objects.all().filter(id=order.product.id)
        ordered_by=models.Customer.objects.all().filter(id = order.customer.id)
        ordered_products.append(ordered_product)
        ordered_bys.append(ordered_by)

    mydict={
    'customercount':customercount,
    'productcount':productcount,
    'ordercount':ordercount,
    'data':zip(ordered_products,ordered_bys,orders),
    }
    return render(request,'ecom/admin_dashboard.html',context=mydict)


# admin view customer table
@login_required(login_url='adminlogin')
def view_customer_view(request):
    customers=models.Customer.objects.all()
    return render(request,'ecom/view_customer.html',{'customers':customers})

# admin delete customer
@login_required(login_url='adminlogin')
def delete_customer_view(request,pk):
    customer=models.Customer.objects.get(id=pk)
    user=models.User.objects.get(id=customer.user_id)
    user.delete()
    customer.delete()
    return redirect('view-customer')


@login_required(login_url='adminlogin')
def update_customer_view(request,pk):
    customer=models.Customer.objects.get(id=pk)
    user=models.User.objects.get(id=customer.user_id)
    userForm=forms.CustomerUserForm(instance=user)
    customerForm=forms.CustomerForm(request.FILES,instance=customer)
    mydict={'userForm':userForm,'customerForm':customerForm}
    if request.method=='POST':
        userForm=forms.CustomerUserForm(request.POST,instance=user)
        customerForm=forms.CustomerForm(request.POST,instance=customer)
        if userForm.is_valid() and customerForm.is_valid():
            user=userForm.save()
            user.set_password(user.password)
            user.save()
            customerForm.save()
            return redirect('view-customer')
    return render(request,'ecom/admin_update_customer.html',context=mydict)

# admin view the product
@login_required(login_url='adminlogin')
def admin_products_view(request):
    products=models.Product.objects.all()
    return render(request,'ecom/admin_products.html',{'products':products})

@login_required(login_url='adminlogin')
def import_products_csv(request):
   # Load form + existing products
    products = Product.objects.all()
    form = ProductCSVForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        csv_file = form.cleaned_data['csv_file']
        # Kiểm tra extension .csv
        if not csv_file.name.lower().endswith('.csv'):
            messages.error(request, 'File phải có định dạng .csv')
            return redirect('import-products-csv')

        # Đọc nội dung
        data_lines = csv_file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(data_lines)
        created = 0

        for idx, row in enumerate(reader, start=1):
            name = row.get('name', '').strip()
            price = row.get('price', '').strip()
            desc  = row.get('description', '').strip()[:40]
            img   = row.get('image', '').strip()

            print(f"[DEBUG] Row {idx}: name={name}, price={price}, image={img}")

            # Tạo đối tượng nhưng chưa save
            try:
                price_int = int(price)
            except ValueError:
                messages.warning(request, f"Row {idx}: Giá không hợp lệ, skip")
                continue

            product = Product(
                name=name + f"_{int(time.time())}",
                price=price_int,
                description=desc
            )

            # Xử lý image
            if img.lower().startswith('http://') or img.lower().startswith('https://'):
                # Download từ URL
                try:
                    resp = requests.get(img, timeout=10)
                    resp.raise_for_status()
                    print(f"[DEBUG] Downloaded {len(resp.content)} bytes from {img}")
                    filename = os.path.basename(img.split('?')[0]) or f"img_{idx}.jpg"
                    product.product_image.save(
                        filename,
                        ContentFile(resp.content),
                        save=False
                    )
                    print(f"[DEBUG] Saved image to product_image/{filename}")
                except Exception as e:
                    print(f"[DEBUG] Error downloading {img}: {e}")
                    messages.warning(request, f"Row {idx}: Không tải được ảnh từ URL")
            else:
                # Fallback static
                static_path = finders.find(img)
                if static_path and os.path.isfile(static_path):
                    with open(static_path, 'rb') as f:
                        data = f.read()
                        product.product_image.save(
                            os.path.basename(img),
                            ContentFile(data),
                            save=False
                        )
                    print(f"[DEBUG] Copied static {img} into media/product_image/")
                else:
                    print(f"[DEBUG] Static image not found: {img}")
                    messages.warning(request, f"Row {idx}: Không tìm thấy static image {img}")

            # Save product
            product.save()
            created += 1

        messages.success(request, f'Imported {created} products!')
        # Sau khi import xong, làm mới form
        return redirect('import-products-csv')

    return render(request, 'ecom/import_products.html', {
        'form': form,
        'products': products,
    })

# admin add product by clicking on floating button
@login_required(login_url='adminlogin')
def admin_add_product_view(request):
    productForm=forms.ProductForm()
    if request.method=='POST':
        productForm=forms.ProductForm(request.POST, request.FILES)
        if productForm.is_valid():
            productForm.save()
        return HttpResponseRedirect('admin-products')
    return render(request,'ecom/admin_add_products.html',{'productForm':productForm})


@login_required(login_url='adminlogin')
def delete_product_view(request,pk):
    product=models.Product.objects.get(id=pk)
    product.delete()
    return redirect('admin-products')


@login_required(login_url='adminlogin')
def update_product_view(request,pk):
    product=models.Product.objects.get(id=pk)
    productForm=forms.ProductForm(instance=product)
    if request.method=='POST':
        productForm=forms.ProductForm(request.POST,request.FILES,instance=product)
        if productForm.is_valid():
            productForm.save()
            return redirect('admin-products')
    return render(request,'ecom/admin_update_product.html',{'productForm':productForm})

# thêm dữ liệu sử dụng chung với transaction
def get_all_orders_data():
    """
    Trả về danh sách dict chứa thông tin từng đơn hàng:
    - product
    - customer
    - order
    """
    from .models import Orders, Product, Customer
    data = []
    orders = Orders.objects.select_related('customer__user', 'product').all()
    for order in orders:
        entry = {
            'order_id': order.id,
            'product': order.product,
            'customer_name': order.customer.user.get_full_name() if order.customer else '',
            'customer_mobile': order.mobile,
            'shipment_address': order.address,
            'status': order.status,
            'order_date': order.order_date,
        }
        data.append(entry)
    return data
@login_required(login_url='adminlogin')
def admin_view_booking_view(request):
    orders_data = get_all_orders_data()
    return render(request, 'ecom/admin_view_booking.html', {'orders_data': orders_data})


@login_required(login_url='adminlogin')
def delete_order_view(request,pk):
    order=models.Orders.objects.get(id=pk)
    order.delete()
    return redirect('admin-view-booking')

# for changing status of order (pending,delivered...)
@login_required(login_url='adminlogin')
def update_order_view(request,pk):
    order=models.Orders.objects.get(id=pk)
    orderForm=forms.OrderForm(instance=order)
    if request.method=='POST':
        orderForm=forms.OrderForm(request.POST,instance=order)
        if orderForm.is_valid():
            orderForm.save()
            return redirect('admin-view-booking')
    return render(request,'ecom/update_order.html',{'orderForm':orderForm})


# admin view the feedback
@login_required(login_url='adminlogin')
def view_feedback_view(request):
    feedbacks=models.Feedback.objects.all().order_by('-id')
    return render(request,'ecom/view_feedback.html',{'feedbacks':feedbacks})



#---------------------------------------------------------------------------------
#------------------------ PUBLIC CUSTOMER RELATED VIEWS START ---------------------
#---------------------------------------------------------------------------------
def search_view(request):
    # whatever user write in search box we get in query
    query = request.GET['query']
    products=models.Product.objects.all().filter(name__icontains=query)
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        counter=product_ids.split('|')
        product_count_in_cart=len(set(counter))
    else:
        product_count_in_cart=0

    # word variable will be shown in html when user click on search button
    word="Searched Result :"

    if request.user.is_authenticated:
        return render(request,'ecom/customer_home.html',{'products':products,'word':word,'product_count_in_cart':product_count_in_cart})
    return render(request,'ecom/index.html',{'products':products,'word':word,'product_count_in_cart':product_count_in_cart})


# any one can add product to cart, no need of signin
def add_to_cart_view(request,pk):
    products=models.Product.objects.all()

    #for cart counter, fetching products ids added by customer from cookies
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        counter=product_ids.split('|')
        product_count_in_cart=len(set(counter))
    else:
        product_count_in_cart=1

    response = render(request, 'ecom/index.html',{'products':products,'product_count_in_cart':product_count_in_cart})

    #adding product id to cookies
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        if product_ids=="":
            product_ids=str(pk)
        else:
            product_ids=product_ids+"|"+str(pk)
        response.set_cookie('product_ids', product_ids)
    else:
        response.set_cookie('product_ids', pk)

    product=models.Product.objects.get(id=pk)
    messages.info(request, product.name + ' added to cart successfully!')

    return response



# for checkout of cart
def cart_view(request):
    #for cart counter
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        counter=product_ids.split('|')
        product_count_in_cart=len(set(counter))
    else:
        product_count_in_cart=0

    # fetching product details from db whose id is present in cookie
    products=None
    total=0
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        if product_ids != "":
            product_id_in_cart=product_ids.split('|')
            products=models.Product.objects.all().filter(id__in = product_id_in_cart)

            #for total price shown in cart
            for p in products:
                total=total+p.price
    return render(request,'ecom/cart.html',{'products':products,'total':total,'product_count_in_cart':product_count_in_cart})


def remove_from_cart_view(request,pk):
    #for counter in cart
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        counter=product_ids.split('|')
        product_count_in_cart=len(set(counter))
    else:
        product_count_in_cart=0

    # removing product id from cookie
    total=0
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        product_id_in_cart=product_ids.split('|')
        product_id_in_cart=list(set(product_id_in_cart))
        product_id_in_cart.remove(str(pk))
        products=models.Product.objects.all().filter(id__in = product_id_in_cart)
        #for total price shown in cart after removing product
        for p in products:
            total=total+p.price

        #  for update coookie value after removing product id in cart
        value=""
        for i in range(len(product_id_in_cart)):
            if i==0:
                value=value+product_id_in_cart[0]
            else:
                value=value+"|"+product_id_in_cart[i]
        response = render(request, 'ecom/cart.html',{'products':products,'total':total,'product_count_in_cart':product_count_in_cart})
        if value=="":
            response.delete_cookie('product_ids')
        response.set_cookie('product_ids',value)
        return response


def send_feedback_view(request):
    feedbackForm=forms.FeedbackForm()
    if request.method == 'POST':
        feedbackForm = forms.FeedbackForm(request.POST)
        if feedbackForm.is_valid():
            feedbackForm.save()
            return render(request, 'ecom/feedback_sent.html')
    return render(request, 'ecom/send_feedback.html', {'feedbackForm':feedbackForm})


#---------------------------------------------------------------------------------
#------------------------ CUSTOMER RELATED VIEWS START ------------------------------
#---------------------------------------------------------------------------------
@login_required(login_url='customerlogin')
@user_passes_test(is_customer)
def customer_home_view(request):
    products=models.Product.objects.all()
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        counter=product_ids.split('|')
        product_count_in_cart=len(set(counter))
    else:
        product_count_in_cart=0
    return render(request,'ecom/customer_home.html',{'products':products,'product_count_in_cart':product_count_in_cart})



# shipment address before placing order
@login_required(login_url='customerlogin')
def customer_address_view(request):
    # this is for checking whether product is present in cart or not
    # if there is no product in cart we will not show address form
    product_in_cart=False
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        if product_ids != "":
            product_in_cart=True
    #for counter in cart
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        counter=product_ids.split('|')
        product_count_in_cart=len(set(counter))
    else:
        product_count_in_cart=0

    addressForm = forms.AddressForm()
    if request.method == 'POST':
        addressForm = forms.AddressForm(request.POST)
        if addressForm.is_valid():
            # here we are taking address, email, mobile at time of order placement
            # we are not taking it from customer account table because
            # these thing can be changes
            email = addressForm.cleaned_data['Email']
            mobile=addressForm.cleaned_data['Mobile']
            address = addressForm.cleaned_data['Address']
            #for showing total price on payment page.....accessing id from cookies then fetching  price of product from db
            total=0
            if 'product_ids' in request.COOKIES:
                product_ids = request.COOKIES['product_ids']
                if product_ids != "":
                    product_id_in_cart=product_ids.split('|')
                    products=models.Product.objects.all().filter(id__in = product_id_in_cart)
                    for p in products:
                        total=total+p.price

            response = render(request, 'ecom/payment.html',{'total':total})
            response.set_cookie('email',email)
            response.set_cookie('mobile',mobile)
            response.set_cookie('address',address)
            return response
    return render(request,'ecom/customer_address.html',{'addressForm':addressForm,'product_in_cart':product_in_cart,'product_count_in_cart':product_count_in_cart})




# here we are just directing to this view...actually we have to check whther payment is successful or not
#then only this view should be accessed
@login_required(login_url='customerlogin')
def payment_success_view(request):
    # Here we will place order | after successful payment
    # we will fetch customer  mobile, address, Email
    # we will fetch product id from cookies then respective details from db
    # then we will create order objects and store in db
    # after that we will delete cookies because after order placed...cart should be empty
    customer=models.Customer.objects.get(user_id=request.user.id)
    products=None
    email=None
    mobile=None
    address=None
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        if product_ids != "":
            product_id_in_cart=product_ids.split('|')
            products=models.Product.objects.all().filter(id__in = product_id_in_cart)
            # Here we get products list that will be ordered by one customer at a time

    # these things can be change so accessing at the time of order...
    if 'email' in request.COOKIES:
        email=request.COOKIES['email']
    if 'mobile' in request.COOKIES:
        mobile=request.COOKIES['mobile']
    if 'address' in request.COOKIES:
        address=request.COOKIES['address']

    for product in products:
        order_obj, created = models.Orders.objects.get_or_create(
            customer=customer,
            product=product,
            status='Pending',
            email=email,
            mobile=mobile,
            address=address
        )
       
    # here we are placing number of orders as much there is a products
    # suppose if we have 5 items in cart and we place order....so 5 rows will be created in orders table
    # there will be lot of redundant data in orders table...but its become more complicated if we normalize it
    for product in products:
        models.Orders.objects.get_or_create(customer=customer,product=product,status='Pending',email=email,mobile=mobile,address=address)

    # after order placed cookies should be deleted
    response = render(request,'ecom/payment_success.html')
    response.delete_cookie('product_ids')
    response.delete_cookie('email')
    response.delete_cookie('mobile')
    response.delete_cookie('address')
    return response




@login_required(login_url='customerlogin')
@user_passes_test(is_customer)
def my_order_view(request):
    customer=models.Customer.objects.get(user_id=request.user.id)
    orders=models.Orders.objects.all().filter(customer_id = customer)
    ordered_products=[]
    for order in orders:
        ordered_product=models.Product.objects.all().filter(id=order.product.id)
        ordered_products.append(ordered_product)

    return render(request,'ecom/my_order.html',{'data':zip(ordered_products,orders)})




#--------------for discharge patient bill (pdf) download and printing
import io
from xhtml2pdf import pisa
from django.template.loader import get_template
from django.template import Context
from django.http import HttpResponse


def render_to_pdf(template_src, context_dict):
    template = get_template(template_src)
    html  = template.render(context_dict)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("ISO-8859-1")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return

@login_required(login_url='customerlogin')
@user_passes_test(is_customer)
def download_invoice_view(request,orderID,productID):
    order=models.Orders.objects.get(id=orderID)
    product=models.Product.objects.get(id=productID)
    mydict={
        'orderDate':order.order_date,
        'customerName':request.user,
        'customerEmail':order.email,
        'customerMobile':order.mobile,
        'shipmentAddress':order.address,
        'orderStatus':order.status,

        'productName':product.name,
        'productImage':product.product_image,
        'productPrice':product.price,
        'productDescription':product.description,


    }
    return render_to_pdf('ecom/download_invoice.html',mydict)






@login_required(login_url='customerlogin')
@user_passes_test(is_customer)
def my_profile_view(request):
    customer=models.Customer.objects.get(user_id=request.user.id)
    return render(request,'ecom/my_profile.html',{'customer':customer})


@login_required(login_url='customerlogin')
@user_passes_test(is_customer)
def edit_profile_view(request):
    customer=models.Customer.objects.get(user_id=request.user.id)
    user=models.User.objects.get(id=customer.user_id)
    userForm=forms.CustomerUserForm(instance=user)
    customerForm=forms.CustomerForm(request.FILES,instance=customer)
    mydict={'userForm':userForm,'customerForm':customerForm}
    if request.method=='POST':
        userForm=forms.CustomerUserForm(request.POST,instance=user)
        customerForm=forms.CustomerForm(request.POST,instance=customer)
        if userForm.is_valid() and customerForm.is_valid():
            user=userForm.save()
            user.set_password(user.password)
            user.save()
            customerForm.save()
            return HttpResponseRedirect('my-profile')
    return render(request,'ecom/edit_profile.html',context=mydict)



#---------------------------------------------------------------------------------
#------------------------ ABOUT US AND CONTACT US VIEWS START --------------------
#---------------------------------------------------------------------------------
def aboutus_view(request):
    return render(request,'ecom/aboutus.html')

def contactus_view(request):
    sub = forms.ContactusForm()
    if request.method == 'POST':
        sub = forms.ContactusForm(request.POST)
        if sub.is_valid():
            email = sub.cleaned_data['Email']
            name=sub.cleaned_data['Name']
            message = sub.cleaned_data['Message']
            send_mail(str(name)+' || '+str(email),message, settings.EMAIL_HOST_USER, settings.EMAIL_RECEIVING_USER, fail_silently = False)
            return render(request, 'ecom/contactussuccess.html')
    return render(request, 'ecom/contactus.html', {'form':sub})


@login_required(login_url='adminlogin')
def view_transactions(request):
    form = TransactionCSVForm()

    # Khởi tạo dữ liệu mặc định nếu không phải POST
    table_data = request.session.get('mafia_data', [])
    freq_table_sorted = []
    maximal_table = []

    # Khi người dùng POST CSV lên
    if request.method == 'POST':
        form = TransactionCSVForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Vui lòng tải lên file CSV.')
            else:
                try:
                    reader = csv.DictReader(TextIOWrapper(csv_file.file, encoding='utf-8'))
                    table_data = []
                    for row in reader:
                        tx_id = row.get('Transaction ID')
                        items_str = row.get('Items')
                        if not tx_id or not items_str:
                            continue
                        # parse items list
                        items = ast.literal_eval(items_str)
                        formatted = ', '.join(sorted(items))
                        # chuẩn bị entry bao gồm thông tin transaction và customer
                        entry = {
                            'order_id': tx_id,
                            'items': formatted,
                            'customer_name': row.get('Customer Name', '').strip(),
                            'customer_mobile': row.get('Customer Mobile', '').strip(),
                            'shipment_address': row.get('Shipment Address', '').strip(),
                        }
                        table_data.append(entry)

                    # Nếu CSV không có đầy đủ customer info, enrich từ DB
                    for entry in table_data:
                        if not entry['customer_name'] or not entry['customer_mobile'] or not entry['shipment_address']:
                            sample_tx = Transaction.objects.filter(order__id=entry['order_id'])\
                                .select_related('order__customer__user','order').first()
                            if sample_tx:
                                cust = sample_tx.order.customer
                                entry['customer_name'] = entry['customer_name'] or cust.user.get_full_name() or cust.user.username
                                entry['customer_mobile'] = entry['customer_mobile'] or sample_tx.order.mobile
                                entry['shipment_address'] = entry['shipment_address'] or sample_tx.order.address

                    request.session['mafia_data'] = table_data
                    messages.success(request, f"Đã import {len(table_data)} giao dịch.")
                    imported_order_ids = {entry['order_id'] for entry in table_data}
                    # Lấy các order khác từ DB không có trong CSV
                    db_data = get_all_orders_data()
                    for entry in db_data:
                        if entry['order_id'] not in imported_order_ids:
                            table_data.append({
                                'order_id': entry['order_id'],
                                'customer_name': entry['customer_name'],
                                'customer_mobile': entry['customer_mobile'],
                                'shipment_address': entry['shipment_address'],
                                'items': entry['product'].name,
                            })
                    # Lưu lại toàn bộ vào session
                    request.session['mafia_data'] = table_data
                except Exception as e:
                    messages.error(request, f"Lỗi xử lý CSV: {e}")
      # 2) ĐỒNG BỘ ĐƠN MỚI TỪ ORDERS VÀO TRANSACTION
    # Loại bỏ những orders đã có trong transactions
    existing_ids = list(Transaction.objects.values_list('order_id', flat=True))
    unsynced_orders = Orders.objects.exclude(id__in=existing_ids)
    for order in unsynced_orders:
        Transaction.objects.create(
            order=order,
            product=order.product,
            quantity=getattr(order, 'quantity', 1)
        )

    if unsynced_orders.exists():
        request.session.pop('mafia_data', None)
    # 3) LOAD DỮ LIỆU CHO VIEW
   # ưu tiên dữ liệu import CSV từ session (nếu là POST CSV)
    order_data = get_all_orders_data()
    
    if not table_data:
        
        grouped = defaultdict(list)
        for entry in order_data:
            grouped[entry['order_id']].append(entry['product'].name)

        table_data = []
        for oid, items in grouped.items():
            sample = next(e for e in order_data if e['order_id'] == oid)
            table_data.append({
                'order_id': oid,
                'customer_name': sample['customer_name'],
                'customer_mobile': sample['customer_mobile'],
                'shipment_address': sample['shipment_address'],
                'items': ', '.join(sorted(items)),
            })
        request.session['mafia_data'] = table_data
    # ưu tiên session sau POST CSV
    if not table_data:
        table_data = request.session.get('mafia_data', [])
        if not table_data:
            qs = Transaction.objects.select_related('order', 'product').all()
            grouped = defaultdict(list)
            for t in qs:
                grouped[t.order.id].append(t.product.name)
            table_data = [
                {'order_id': oid, 'items': ', '.join(sorted(items))}
                for oid, items in grouped.items()
            ]
            request.session['mafia_data'] = table_data
    # Tính tần suất sản phẩm nếu có dữ liệu
    if table_data:
        # Tần suất sản phẩm
        freq_count = {}
        for row in table_data:
            items = [i.strip() for i in row['items'].split(',')]
            for item in items:
                freq_count.setdefault(item, set()).add(row['order_id'])
        freq_table = [{'product_name': p, 'order_ids': sorted([str(i) for i in ids]), 'count': len(ids)} for p, ids in freq_count.items()]

        freq_table_sorted = sorted(freq_table, key=lambda x: -x['count'])

        # Chuẩn bị transactions list
        transactions = [[i.strip() for i in row['items'].split(',')] for row in table_data]

        # Gọi hàm tích hợp MAFIA và luật kết hợp
        maximal_sets, rules = find_maximal_itemsets_and_rules(transactions, min_support=0.3, min_confidence=0.6)

        # Format maximal itemsets
        maximal_table = [{'index': idx+1, 'itemset': ', '.join(sorted(m)), 'length': len(m)}
                         for idx, m in enumerate(maximal_sets)]
        # Format rules
        rules_table = [
            {'antecedent': ', '.join(sorted(a)),
             'consequent': ', '.join(sorted(b)),
             'support': supp,
             'confidence': conf,
             'lift': lift}
            for (a, b, supp, conf, lift) in rules
        ]
        request.session['mafia_maximal_itemsets'] = [list(s) for s in maximal_sets]

    return render(request, 'ecom/view_transactions_mafia.html', {
        'form': form,
        'table_data': table_data,
        'freq_table': freq_table_sorted,
        'maximal_table': maximal_table
    })



@login_required(login_url='adminlogin')
def basket_market_view(request):
    result = []
    min_support = float(request.GET.get('min_support', 0.3))

    transactions = request.session.get('mafia_data', [])
    if not transactions:
        messages.warning(request, "Vui lòng import transaction trước.")
        return redirect('view-transactions')

    basket = [[item.strip() for item in row['items'].split(',')] for row in transactions]

    from .mafia import find_maximal_itemsets
    maximal_sets = find_maximal_itemsets(basket, min_support=min_support)

    result = [{
        'index': i + 1,
        'itemset': ', '.join(sorted(itemset)),
        'length': len(itemset)
    } for i, itemset in enumerate(maximal_sets)]

    return render(request, 'ecom/basket_market.html', {
        'result': result,
        'min_support': min_support
    })

@login_required(login_url='adminlogin')
def mafia_recommend_view(request):
    maximal_itemsets = request.session.get('mafia_maximal_itemsets', [])
    recommendations = []
    input_items = []

    if request.method == 'POST':
        input_items_str = request.POST.get('basket', '')
        try:
            input_items = [i.strip() for i in input_items_str.split(',') if i.strip()]
            input_set = set(input_items)

            for mfi in maximal_itemsets:
                mfi_set = set(mfi)
                if input_set.issubset(mfi_set) and input_set != mfi_set:
                    recommendations.append({
                        'from': ', '.join(input_items),
                        'suggest': ', '.join(sorted(mfi_set - input_set))
                    })

        except Exception as e:
            messages.warning(request, f"Lỗi: {str(e)}")

    return render(request, 'ecom/mafia_recommend.html', {
        'input_items': input_items,
        'recommendations': recommendations
    })

def generate_association_rules(mfi_itemsets, transactions, min_confidence):
    from itertools import chain, combinations
    import math

    # Đếm số giao dịch chứa mỗi itemset
    def count_support(itemset):
        return sum(1 for t in transactions if itemset.issubset(set(t)))

    rules = []
    total_transactions = len(transactions)

    for itemset in mfi_itemsets:
        itemset = set(itemset)
        if len(itemset) < 2:
            continue

        for i in range(1, len(itemset)):
            for lhs in combinations(itemset, i):
                lhs = set(lhs)
                rhs = itemset - lhs
                if not rhs:
                    continue

                lhs_support_count = count_support(lhs)
                full_support_count = count_support(itemset)

                if lhs_support_count == 0:
                    continue

                confidence = full_support_count / lhs_support_count

                if confidence >= min_confidence:
                    rhs_support_count = count_support(rhs)
                    lift = confidence / (rhs_support_count / total_transactions) if rhs_support_count > 0 else 0
                    rules.append({
                        'lhs': ', '.join(sorted(lhs)),
                        'rhs': ', '.join(sorted(rhs)),
                        'support': round(full_support_count / total_transactions, 2),
                        'confidence': round(confidence, 2),
                        'lift': round(lift, 2),
                        'frequency': full_support_count
                    })

    return sorted(rules, key=lambda x: (-x['confidence'], -x['support']))


@login_required(login_url='adminlogin')
def mafia_recommend_view(request):
    from .mafia import find_maximal_itemsets
    import itertools

    table_data = request.session.get('mafia_data', [])
    transactions = [[item.strip() for item in row['items'].split(',')] for row in table_data]

    recommendations = []
    input_items = []

    min_conf_str = str(request.GET.get('min_conf', '0.5')).replace(',', '.')
    min_conf = float(min_conf_str)

    if request.method == 'POST':
        basket_raw = request.POST.get('basket', '')
        input_items = [item.strip() for item in basket_raw.split(',') if item.strip()]

        if input_items:
            # Tính minsup từ dữ liệu đã lưu
            minsup_ratio = float(request.GET.get('minsup', 0.3))
            minsup = max(int(minsup_ratio * len(transactions)), 1)
            tidsets = defaultdict(set)
            for tid, transaction in enumerate(transactions):
                for item in transaction:
                    tidsets[item].add(tid)

            all_tids = set(range(len(transactions)))
            items = sorted(tidsets.keys())
            MFI = []
            mafia(set(), items, tidsets, minsup, MFI, all_tids)

            # Sinh luật từ tập phổ biến cực đại
            rules = []
            for itemset in MFI:
                if len(itemset) < 2:
                    continue
                for i in range(1, len(itemset)):
                    for lhs in itertools.combinations(itemset, i):
                        lhs = set(lhs)
                        rhs = itemset - lhs
                        lhs_support = sum(1 for t in transactions if lhs.issubset(t))
                        both_support = sum(1 for t in transactions if lhs.union(rhs).issubset(t))

                        if lhs_support == 0:
                            continue

                        conf = both_support / lhs_support

                        if conf >= min_conf:
                            rules.append({
                                'lhs': lhs,
                                'rhs': rhs,
                                'confidence': conf
                            })

            # Áp dụng luật cho giỏ hàng hiện tại
            for rule in rules:
                if rule['lhs'].issubset(set(input_items)):
                    suggest_items = rule['rhs'] - set(input_items)
                    if suggest_items:
                        recommendations.append({
                            'from': ', '.join(sorted(rule['lhs'])),
                            'suggest': ', '.join(sorted(suggest_items))
                        })

    return render(request, 'ecom/mafia_recommend.html', {
        'recommendations': recommendations,
        'input_items': input_items
    })
