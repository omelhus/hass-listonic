# Listonic API Documentation

Base URL: `https://api.listonic.com`

**Note:** This integration is not affiliated with Listonic in any way. This API documentation was reverse-engineered from the Listonic web app for educational and personal use.

## Authentication

### Login with Email/Password
```
POST /api/loginextended?provider=password&autoMerge=1&autoDestruct=1
```

**Headers**:
```
Content-Type: application/x-www-form-urlencoded
clientauthorization: Bearer <base64(client_id:client_secret)>
```

The `clientauthorization` header uses base64 encoding of `listonicv2:fjdfsoj9874jdfhjkh34jkhffdfff`.

**Request Body** (form-urlencoded):
```
username=user@example.com
password=password
client_id=listonicv2
client_secret=fjdfsoj9874jdfhjkh34jkhffdfff
redirect_uri=https://listonicv2api.jestemkucharzem.pl
```

**Response**:
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "Bearer",
  "expires_in": 86399,
  "refresh_token": "..."
}
```

The `access_token` is used in subsequent requests via the `Authorization: Bearer <token>` header.

### Anonymous Account
```
POST /api/anonymousaccount
```

Creates an anonymous account for unauthenticated users. Returns temporary credentials.

---

## Lists

### Get All Lists
```
GET /api/lists?includeShares=true&archive=false&includeItems=true
```

**Query Parameters**:
- `includeShares` (boolean): Include shared list information
- `archive` (boolean): Include archived lists
- `includeItems` (boolean): Include items in each list

**Response**: Array of list objects with items

### Get Single List
```
GET /api/lists/{listId}?includeShares=true
```

**Path Parameters**:
- `listId` (integer): The list ID

**Query Parameters**:
- `includeShares` (boolean): Include shared list information

### Create List
```
POST /api/lists
```

**Request Body**:
```json
{
  "name": "List Name"
}
```

**Response**: 201 Created with the new list object

### Delete List
```
DELETE /api/lists/{listId}
```

Moves the list to trash.

---

## List Items

### Get List Items
```
GET /api/lists/{listId}/items
```

**Path Parameters**:
- `listId` (integer): The list ID

**Response**: Array of item objects

### Add Item to List
```
POST /api/lists/{listId}/items
```

**Path Parameters**:
- `listId` (integer): The list ID

**Request Body**:
```json
{
  "name": "Item Name",
  "quantity": "1",
  "unit": "kg",
  "price": "3.99",
  "description": "Optional description",
  "categoryId": 123
}
```

**Response**: 201 Created with the new item object

### Update Item
```
PATCH /api/lists/{listId}/items/{itemId}
```

**Path Parameters**:
- `listId` (integer): The list ID
- `itemId` (integer): The item ID

**Request Body** (partial update):
```json
{
  "isChecked": true,
  "name": "Updated Name",
  "quantity": "2"
}
```

Used for:
- Checking/unchecking items (toggle `isChecked`)
- Updating item details (name, quantity, unit, price, description, category)

### Delete Item
```
DELETE /api/lists/{listId}/items/{itemId}
```

**Path Parameters**:
- `listId` (integer): The list ID
- `itemId` (integer): The item ID

**Response**: 200 OK

---

## Account

### Get User Info
```
GET /api/account/userinfo
```

Returns basic user information.

### Get User Profile
```
GET /api/account/profile
```

Returns detailed user profile information.

---

## Categories

### Get Categories
```
GET /api/categoriesv2
```

Returns list of product categories for organizing items.

### Get Category Icons
```
GET /api/categoryicons
```

Returns icons for categories.

---

## Other Endpoints

### Get Prompter (Suggestions)
```
GET /api/prompter
```

Returns product suggestions for the add product input.

---

## Authentication Headers

The API uses token-based authentication. After login, include the token in requests:

```
Authorization: Bearer {token}
```

The exact header format needs to be verified by inspecting the login response.

---

## Notes

- API uses HTTPS
- All endpoints return JSON
- Firebase is used for:
  - Remote config
  - Installations
  - Push notifications (likely)
- The web app is built with Next.js
- List IDs and Item IDs are integers (e.g., 198563329, 10902813372)

---

## Discovered List Structure

Based on observation:
- Lists have: id, name, items, shares, archive status
- Items have: id, name, isChecked, quantity, unit, price, description, categoryId
- Shares show collaborators with their email addresses

---

## API Behavior

- Creating an item: POST returns 201 Created
- Updating an item: PATCH returns 200 OK (empty body)
- Deleting an item: DELETE returns 200 OK
- Items can be checked/unchecked via PATCH with `Checked` field (1/0)

## Field Naming Convention

The API uses **PascalCase** for all field names in both requests and responses:

### List Fields
- `Id` (string) - List ID
- `Name` - List name
- `Items` - Array of items
- `Active` (1/0) - Whether list is active
- `Deleted` (1/0) - Whether list is deleted

### Item Fields
- `Id` (string) - Item ID
- `IdAsNumber` (int) - Numeric item ID
- `Name` - Item name
- `Checked` (1/0) - Whether item is checked
- `Amount` - Quantity (string)
- `Unit` - Unit of measurement
- `Price` - Price (float)
- `Description` - Item description
- `CategoryId` - Category ID
