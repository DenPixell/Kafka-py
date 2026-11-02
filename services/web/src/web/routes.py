from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from web import session as store
from web.clients.catalog import CatalogClient
from web.clients.orders import OrderClient
from web.formatting import COUNTRIES

router = APIRouter()


def get_catalog(request: Request) -> CatalogClient:
    client: CatalogClient = request.app.state.catalog
    return client


def get_orders(request: Request) -> OrderClient:
    client: OrderClient = request.app.state.orders
    return client


Catalog = Annotated[CatalogClient, Depends(get_catalog)]
Orders = Annotated[OrderClient, Depends(get_orders)]


def render(request: Request, template: str, status_code: int = 200, **context: object) -> Response:
    templates = request.app.state.templates
    response: Response = templates.TemplateResponse(
        request,
        template,
        {
            "buyer": store.current_buyer(request.session),
            "buyers": store.BUYERS,
            "cart_count": sum(store.cart(request.session).values()),
            **context,
        },
        status_code=status_code,
    )
    return response


def redirect(url: str) -> RedirectResponse:
    # 303: после POST браузер переходит по адресу через GET, повторная отправка формы
    # при обновлении страницы невозможна.
    return RedirectResponse(url, status_code=303)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, catalog: Catalog) -> Response:
    categories = await catalog.categories()
    products = await catalog.products() or []
    sections = [(c, [p for p in products if p.category_slug == c.slug]) for c in categories]
    return render(request, "home.html", sections=sections)


@router.get("/catalog/{category}", response_class=HTMLResponse)
async def category_page(request: Request, catalog: Catalog, category: str) -> Response:
    products = await catalog.products(category)
    if products is None:
        raise HTTPException(404)
    categories = {c.slug: c for c in await catalog.categories()}
    return render(request, "category.html", category=categories[category], products=products)


@router.get("/products/{slug}", response_class=HTMLResponse)
async def product_page(request: Request, catalog: Catalog, slug: str) -> Response:
    product = await catalog.product(slug)
    if product is None:
        raise HTTPException(404)
    default = next((v for v in product.variants if v.in_stock), None)
    return render(request, "product.html", product=product, default=default)


@router.post("/cart/add")
async def add_to_cart(request: Request, sku: Annotated[str, Form()]) -> Response:
    store.add_to_cart(request.session, sku)
    return redirect("/cart")


@router.post("/cart/update")
async def update_cart(
    request: Request, sku: Annotated[str, Form()], quantity: Annotated[int, Form()]
) -> Response:
    store.set_quantity(request.session, sku, quantity)
    return redirect("/cart")


@router.get("/cart", response_class=HTMLResponse)
async def cart_page(request: Request, catalog: Catalog) -> Response:
    items = store.cart(request.session)
    variants = {v.sku: v for v in await catalog.variants(list(items))}
    # Артикулы, которых больше нет в каталоге, из корзины убираем.
    lines = [(variants[sku], qty) for sku, qty in items.items() if sku in variants]
    total = sum(v.price_kopecks * qty for v, qty in lines)
    return render(request, "cart.html", lines=lines, total=total, countries=COUNTRIES)


@router.post("/checkout")
async def checkout(
    request: Request, orders: Orders, delivery_country: Annotated[str, Form()]
) -> Response:
    items = store.cart(request.session)
    if not items or delivery_country not in COUNTRIES:
        return redirect("/cart")
    order = await orders.create(store.current_buyer(request.session), items, delivery_country)
    store.clear_cart(request.session)
    return redirect(f"/orders/{order.id}")


@router.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request, orders: Orders) -> Response:
    return render(
        request, "orders.html", orders=await orders.list(store.current_buyer(request.session))
    )


@router.get("/orders/{order_id}", response_class=HTMLResponse)
async def order_page(
    request: Request, orders: Orders, catalog: Catalog, order_id: UUID
) -> Response:
    order = await orders.get(store.current_buyer(request.session), order_id)
    if order is None:
        raise HTTPException(404)
    names = {v.sku: v for v in await catalog.variants([i.sku for i in order.items])}
    return render(request, "order.html", order=order, variants=names)


@router.get("/orders/{order_id}/status", response_class=HTMLResponse)
async def order_status(request: Request, orders: Orders, order_id: UUID) -> Response:
    """Фрагмент со статусом: HTMX запрашивает его раз в секунду, пока статус не финальный."""
    order = await orders.get(store.current_buyer(request.session), order_id)
    if order is None:
        raise HTTPException(404)
    return render(request, "_order_status.html", order=order)


@router.post("/buyer")
async def switch_buyer(
    request: Request, buyer: Annotated[str, Form()], next_url: Annotated[str, Form()] = "/"
) -> Response:
    store.set_buyer(request.session, buyer)
    # Чужой заказ новому покупателю не откроется, поэтому со страницы заказа — к списку.
    if next_url.startswith("/orders/"):
        return redirect("/orders")
    # Только относительный адрес этого же сайта: «//evil.example» тоже начинается со «/».
    return redirect(next_url if next_url.startswith("/") and not next_url.startswith("//") else "/")
