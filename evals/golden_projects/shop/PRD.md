# Shop — Product Requirements (golden project 1)

Version 1.0 · used only to evaluate Smart QA. The seeded-bug list is kept in `evals/private/`.

## 1. Roles

Customers can browse products, keep a cart and place orders.
Administrators can add products and change prices.
Guests can browse products but cannot place orders.

## 2. Sign up and log in

A customer signs up with an email address and a password.
REQ-AUTH-1: The password must be 8 to 64 characters long.
REQ-AUTH-2: The email address must be unique; signing up twice with the same email shows "Email already registered".
REQ-AUTH-3: After 5 failed log-in attempts the account is locked for 15 minutes.

## 3. Browse and search

Customers and guests can search products by name.
REQ-SRCH-1: Search results must load fast.
REQ-SRCH-2: Each results page shows at most 20 products.

## 4. Cart

A customer adds products to the cart from the product page.
REQ-CART-1: A customer can add at most 10 units of one product to the cart.
REQ-CART-2: The cart total is the sum of unit price times quantity for every line.

## 5. Checkout

A customer checks out from the cart page by entering a shipping address and paying by card.
REQ-CHK-1: Orders of 50 dollars or more get free shipping.
REQ-CHK-2: A coupon code gives 10 percent off the cart total.
REQ-CHK-3: A coupon expires 30 days after it is issued.
REQ-CHK-4: An expired coupon is rejected with the message "Coupon expired".

## 6. Orders

A customer sees past orders on the order history page.
REQ-ORD-1: An order can be cancelled within 24 hours of being placed.

## 7. Administration

An administrator adds products on the admin products page.
REQ-ADM-1: A product price must be greater than 0.
