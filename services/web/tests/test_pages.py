import httpx

from .backend import FakeBackend


async def add_neo_512(client: httpx.AsyncClient) -> None:
    await client.post("/cart/add", data={"sku": "macbook-neo-512-silver"})


async def test_home_lists_products_with_formatted_price(client: httpx.AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert "MacBook Neo" in response.text
    assert "от 69 990 ₽" in response.text


async def test_unknown_category_is_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/catalog/watch")

    assert response.status_code == 404
    assert "Страница не найдена" in response.text


async def test_product_page_preselects_first_available_configuration(
    client: httpx.AsyncClient,
) -> None:
    text = (await client.get("/products/macbook-neo")).text

    # Серебристый 256 ГБ закончился, поэтому выбран первый в наличии — серебристый 512.
    assert 'name="sku" value="macbook-neo-512-silver"' in text
    assert "с Touch ID" in text
    assert "neo-silver-1.jpg" in text


async def test_product_page_respects_requested_color(client: httpx.AsyncClient) -> None:
    text = (await client.get("/products/macbook-neo?color=citrus")).text

    assert 'name="sku" value="macbook-neo-256-citrus"' in text
    assert "neo-citrus-1.jpg" in text
    assert "neo-silver-1.jpg" not in text


async def test_configure_fragment_is_a_block_not_a_page(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/products/macbook-neo/configure", params={"color": "citrus", "storage": "512"}
    )

    assert response.status_code == 200
    assert response.text.lstrip().startswith('<article class="config config--row"')
    assert "Нет в наличии" in response.text
    assert "disabled" in response.text


async def test_catalog_filter_by_model(client: httpx.AsyncClient) -> None:
    text = (await client.get("/catalog/mac?model=macbook-neo")).text

    assert 'class="pill is-active" href="/catalog/mac?model=macbook-neo"' in text
    assert text.count('class="config config--row"') == 1


async def test_cart_keeps_items_between_requests(client: httpx.AsyncClient) -> None:
    await add_neo_512(client)
    await add_neo_512(client)

    text = (await client.get("/cart")).text

    assert 'aria-label="Количество">2<' in text
    assert "159 980 ₽" in text


async def test_quantity_zero_removes_line(client: httpx.AsyncClient) -> None:
    await add_neo_512(client)

    await client.post("/cart/update", data={"sku": "macbook-neo-512-silver", "quantity": "0"})

    assert "В корзине пока пусто" in (await client.get("/cart")).text


async def test_checkout_creates_order_for_current_buyer_and_clears_cart(
    client: httpx.AsyncClient, backend: FakeBackend
) -> None:
    await client.post("/buyer", data={"buyer": "vera", "next_url": "/cart"})
    await add_neo_512(client)

    response = await client.post("/checkout", data={"delivery_country": "AM"})

    assert response.status_code == 303
    assert response.headers["location"].startswith("/orders/")
    assert backend.created == [
        (
            "vera",
            {"items": [{"sku": "macbook-neo-512-silver", "quantity": 1}], "delivery_country": "AM"},
        )
    ]
    assert "В корзине пока пусто" in (await client.get("/cart")).text


async def test_unknown_country_does_not_create_order(
    client: httpx.AsyncClient, backend: FakeBackend
) -> None:
    await add_neo_512(client)

    await client.post("/checkout", data={"delivery_country": "XX"})

    assert backend.created == []


async def test_status_fragment_polls_until_final(
    client: httpx.AsyncClient, backend: FakeBackend
) -> None:
    await add_neo_512(client)
    order_url = (await client.post("/checkout", data={"delivery_country": "RU"})).headers[
        "location"
    ]
    order = next(iter(backend.orders.values()))

    polling = (await client.get(f"{order_url}/status")).text
    order.update(status="CONFIRMED", total_kopecks=7_999_000)
    final = (await client.get(f"{order_url}/status")).text

    assert 'hx-trigger="every 1s"' in polling
    assert "Резервируем товар" in polling
    assert "hx-get" not in final
    assert "Подтверждён" in final


async def test_other_buyer_cannot_see_order(client: httpx.AsyncClient) -> None:
    await add_neo_512(client)
    order_url = (await client.post("/checkout", data={"delivery_country": "RU"})).headers[
        "location"
    ]

    await client.post("/buyer", data={"buyer": "boris", "next_url": order_url})

    assert (await client.get(order_url)).status_code == 404


async def test_buyer_switch_does_not_redirect_to_other_sites(client: httpx.AsyncClient) -> None:
    response = await client.post("/buyer", data={"buyer": "gleb", "next_url": "//evil.example"})

    assert response.headers["location"] == "/"


async def test_unavailable_service_shows_503(
    client: httpx.AsyncClient, backend: FakeBackend
) -> None:
    backend.down = True

    response = await client.get("/")

    assert response.status_code == 503
    assert "временно недоступен" in response.text


async def test_order_time_is_shown_in_moscow_time(
    client: httpx.AsyncClient, backend: FakeBackend
) -> None:
    await add_neo_512(client)
    order_url = (await client.post("/checkout", data={"delivery_country": "RU"})).headers[
        "location"
    ]

    text = (await client.get(order_url)).text

    # В бэкенде заказ создан в 12:00 UTC.
    assert "02.11.2026 15:00" in text


async def test_total_appears_in_status_fragment_once_known(
    client: httpx.AsyncClient, backend: FakeBackend
) -> None:
    await add_neo_512(client)
    order_url = (await client.post("/checkout", data={"delivery_country": "RU"})).headers[
        "location"
    ]
    next(iter(backend.orders.values())).update(status="FRAUD_CHECK", total_kopecks=7_999_000)

    fragment = (await client.get(f"{order_url}/status")).text

    assert "79 990 ₽" in fragment
