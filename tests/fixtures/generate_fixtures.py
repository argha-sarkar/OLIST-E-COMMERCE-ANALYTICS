"""Regenerate the tiny fixture dataset used by the tests and by CI.

It is deliberately small (6 orders) and hand-built so every edge case in this
project is covered:
  - a repeat customer and a one-timer      -> RFM / repeat rate
  - one late order and one on-time order    -> delivery + t-test
  - one cancelled order                     -> revenue filter
  - a category with no translation row      -> LEFT JOIN behaviour
  - a duplicated review_id                  -> dedup rule
  - a multi-item, multi-seller order        -> grain checks
Run:  python tests/fixtures/generate_fixtures.py
"""
from __future__ import annotations

import csv
from pathlib import Path

OUT = Path(__file__).resolve().parent / "raw"

CUSTOMERS = [
    # customer_id, customer_unique_id, zip, city, state
    ("cust_o1", "cu1", "01001", "sao paulo", "SP"),
    ("cust_o2", "cu2", "20040", "rio de janeiro", "RJ"),
    ("cust_o3", "cu1", "01001", "sao paulo", "SP"),
    ("cust_o4", "cu3", "01001", "sao paulo", "SP"),
    ("cust_o5", "cu3", "01001", "sao paulo", "SP"),
    ("cust_o6", "cu4", "80000", "curitiba", "PR"),
]

ORDERS = [
    # order_id, customer_id, status, purchase, approved, carrier, delivered, estimated
    ("o1", "cust_o1", "delivered", "2017-01-05 10:00:00", "2017-01-05 12:00:00",
     "2017-01-07 09:00:00", "2017-01-12 15:00:00", "2017-01-15 00:00:00"),
    ("o2", "cust_o2", "delivered", "2017-01-10 09:00:00", "2017-01-10 11:00:00",
     "2017-01-12 10:00:00", "2017-01-25 18:00:00", "2017-01-20 00:00:00"),
    ("o3", "cust_o3", "delivered", "2017-02-02 14:00:00", "2017-02-02 15:00:00",
     "2017-02-04 08:00:00", "2017-02-09 11:00:00", "2017-02-12 00:00:00"),
    ("o4", "cust_o4", "canceled", "2017-02-10 08:00:00", "2017-02-10 09:00:00",
     "", "", "2017-02-20 00:00:00"),
    ("o5", "cust_o5", "delivered", "2017-02-15 10:00:00", "2017-02-15 11:00:00",
     "2017-02-17 09:00:00", "2017-02-22 16:00:00", "2017-02-25 00:00:00"),
    ("o6", "cust_o6", "delivered", "2017-03-01 09:00:00", "2017-03-01 10:00:00",
     "2017-03-03 10:00:00", "2017-03-20 12:00:00", "2017-03-10 00:00:00"),
]

ITEMS = [
    # order_id, item_id, product_id, seller_id, shipping_limit, price, freight
    ("o1", 1, "p1", "s1", "2017-01-08 00:00:00", "100.00", "15.00"),
    ("o2", 1, "p2", "s2", "2017-01-13 00:00:00", "50.00", "10.00"),
    ("o3", 1, "p1", "s1", "2017-02-05 00:00:00", "100.00", "15.00"),
    ("o3", 2, "p3", "s3", "2017-02-05 00:00:00", "200.00", "20.00"),
    ("o4", 1, "p2", "s2", "2017-02-13 00:00:00", "50.00", "10.00"),
    ("o5", 1, "p4", "s3", "2017-02-18 00:00:00", "300.00", "25.00"),
    ("o6", 1, "p3", "s3", "2017-03-04 00:00:00", "200.00", "20.00"),
]

PAYMENTS = [
    ("o1", 1, "credit_card", 1, "115.00"),
    ("o2", 1, "boleto", 1, "60.00"),
    ("o3", 1, "credit_card", 2, "100.00"),
    ("o3", 2, "voucher", 1, "235.00"),
    ("o4", 1, "credit_card", 1, "60.00"),
    ("o5", 1, "credit_card", 3, "325.00"),
    ("o6", 1, "debit_card", 1, "220.00"),
]

REVIEWS = [
    # review_id, order_id, score, title, message, creation, answer
    ("r1", "o1", 5, "otimo", "chegou antes do prazo", "2017-01-13 00:00:00", "2017-01-13 10:00:00"),
    ("r2", "o2", 1, "atraso", "chegou muito atrasado", "2017-01-26 00:00:00", "2017-01-26 10:00:00"),
    ("r3", "o3", 5, "", "", "2017-02-10 00:00:00", "2017-02-10 10:00:00"),
    ("r4", "o5", 4, "bom", "produto bom", "2017-02-23 00:00:00", "2017-02-25 10:00:00"),
    # earlier answer for the same order: the dedup rule must keep r4, not this one
    ("r6", "o5", 3, "ok", "razoavel", "2017-02-23 00:00:00", "2017-02-24 10:00:00"),
    ("r5", "o6", 2, "atrasado", "demorou demais", "2017-03-21 00:00:00", "2017-03-21 10:00:00"),
]

PRODUCTS = [
    # id, category, name_len, desc_len, photos, weight, l, h, w
    ("p1", "beleza_saude", 40, 287, 1, 225, 15, 10, 20),
    ("p2", "esporte_lazer", 45, 300, 2, 500, 20, 15, 25),
    ("p3", "beleza_saude", 38, 250, 1, 300, 18, 12, 22),
    ("p4", "pc_gamer", 50, 400, 3, 1200, 30, 20, 35),
]

SELLERS = [
    ("s1", "01001", "sao paulo", "SP"),
    ("s2", "20040", "rio de janeiro", "RJ"),
    ("s3", "80000", "curitiba", "PR"),
]

GEOLOCATION = [
    ("01001", -23.5505, -46.6333, "sao paulo", "SP"),
    ("01001", -23.5480, -46.6400, "sao paulo", "SP"),
    ("20040", -22.9068, -43.1729, "rio de janeiro", "RJ"),
    ("80000", -25.4284, -49.2733, "curitiba", "PR"),
]

TRANSLATION = [
    ("beleza_saude", "health_beauty"),
    ("esporte_lazer", "sports_leisure"),
]


def _write(name, header, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print("wrote", name, len(rows), "rows")


def main():
    _write("olist_customers_dataset.csv",
           ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"],
           CUSTOMERS)
    _write("olist_orders_dataset.csv",
           ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
            "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"],
           ORDERS)
    _write("olist_order_items_dataset.csv",
           ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"],
           ITEMS)
    _write("olist_order_payments_dataset.csv",
           ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"],
           PAYMENTS)
    _write("olist_order_reviews_dataset.csv",
           ["review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
            "review_creation_date", "review_answer_timestamp"],
           REVIEWS)
    _write("olist_products_dataset.csv",
           ["product_id", "product_category_name", "product_name_lenght", "product_description_lenght",
            "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"],
           PRODUCTS)
    _write("olist_sellers_dataset.csv",
           ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
           SELLERS)
    _write("olist_geolocation_dataset.csv",
           ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state"],
           GEOLOCATION)
    _write("product_category_name_translation.csv",
           ["product_category_name", "product_category_name_english"],
           TRANSLATION)


if __name__ == "__main__":
    main()
