from apps.core.generic import ProtectedCreateView, ScopedModelListView

from .forms import ProductForm
from .models import Product


class ProductListView(ScopedModelListView):
    model = Product
    page_title = "Products"
    columns = (
        {"label": "SKU", "field": "sku"},
        {"label": "Product", "field": "name"},
        {"label": "Category", "field": "category"},
        {"label": "Unit price", "field": "selling_price"},
        {"label": "Stock", "field": "stock_on_hand"},
    )
    search_fields = ("sku", "name", "category")
    create_url_name = "products:create"
    create_permission = "products.add_product"


class ProductCreateView(ProtectedCreateView):
    model = Product
    form_class = ProductForm
    page_title = "Add product"
    success_url_name = "products:list"