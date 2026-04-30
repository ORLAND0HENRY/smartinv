# 📈 Smart Inventory: Predictive SME Analytics Engine

**Smart Inventory** is an advanced resource planning and sales tracking system built to empower SMEs with data-driven decision-making. By leveraging real-time database aggregations and atomic transaction processing, it ensures total data integrity for business operations.

## 🚀 Key Features

### 1. Real-Time Business Intelligence
The central dashboard provides an immediate snapshot of organizational health:
* **Monthly Performance:** Automated tracking of sale counts and revenue for the current month[cite: 1].
* **Stock Health Monitoring:** Priority listing of low-stock items (quantity $\le 10$) to prevent supply chain disruptions[cite: 1].
* **Valuation Analytics:** Instant calculation of total inventory value and overall sales performance[cite: 1].

### 2. Atomic Sales Processing
To ensure financial accuracy, the system implements a robust "all-or-nothing" transaction protocol:
* **`transaction.atomic`:** Guarantees that sales records and multiple line items are saved simultaneously; if one fails, the entire transaction rolls back to prevent data corruption[cite: 1].
* **Dynamic Totaling:** Automatically updates the `sale.total_amount` server-side after items are confirmed, ensuring consistency between line items and global records[cite: 1].

### 3. High-Performance Query Architecture
Designed for scalability, the system optimizes database interaction to handle large inventories:
* **$N+1$ Prevention:** Utilizes `select_related` for categories and users to fetch related data in a single SQL join[cite: 1].
* **Efficient Lookups:** Uses `prefetch_related` for nested many-to-many relationships (Sale Items $\to$ Products) to keep the UI snappy even with deep transaction history[cite: 1].

## 🛠️ Technical Stack
* **Backend:** Python / Django 5.0[cite: 1].
* **Database Logic:** PostgreSQL-ready with advanced Django ORM aggregations (`Sum`, `Count`)[cite: 1].
* **Security:** Integrated `permission_required` decorators to gate sensitive actions like deleting products or recording sales[cite: 1].
* **Logging:** Comprehensive `logging` integration to track and debug transaction failures in production environments[cite: 1].

## 📂 View Logic Implementation Detail

| View | Strategy | Technical Highlight |
| :--- | :--- | :--- |
| `dashboard` | Statistical Aggregation | Merges `Count` and `Sum` in a single query filter[cite: 1]. |
| `record_sale` | Atomic Formsets | Manages complex parent-child relationships securely[cite: 1]. |
| `sale_detail` | Data Prefetching | Minimizes database hits for high-detail audit logs[cite: 1]. |

---
**Developed by:** Orlantech Innovations 
**Theme:** Amber-500 Signature
