

# SOFTWARE REQUIREMENTS SPECIFICATION (SRS)

**Project:** PSX Portfolio Analytics Tracker
**Document Owner:** Lead Architecture
**Status:** Approved for Initial Development Sprint

## 1. Executive Summary

A bespoke web application enabling users to log personal trades on the Pakistan Stock Exchange (PSX), fetch automated daily price updates, and visualize portfolio performance through high-fidelity, interactive dashboards. The system emphasizes accurate return calculations (TWR/MWR), automated handling of regional corporate actions, and a premium, cinematic user interface.


## 3. Departmental Deliverables

### 3.1 Backend Engineering (Python/Flask/SQLAlchemy)

The backend is responsible for data integrity, scheduled ingestion, and complex financial calculations.

* **REQ-B1 (Data Ingestion):** Implement a daily scheduled job (e.g., using APScheduler) running at 17:00 PKT to fetch End-of-Day (EOD) pricing via the `psxdata` library for all active portfolio tickers.
* **REQ-B2 (Database Schema):** Design a relational database (PostgreSQL recommended) with tables for `Users`, `Portfolios`, `Transactions` (Buy/Sell, Date, Price, Qty, Fees), and `Daily_Prices`.
* **REQ-B3 (Tax-Lot Accounting):** Implement an algorithm to process sales using the Average Cost method to accurately calculate realized gains.
* **REQ-B4 (Performance Engine):** Create API endpoints that return pre-calculated portfolio metrics, specifically Time-Weighted Return (TWR), total Unrealized P&L, and sector exposure percentages.
* **REQ-B5 (Corporate Action Logic):** Develop a script to adjust historical cost bases and quantities upon the declaration of stock splits or bonus shares on the PSX.

### 3.2 Frontend Engineering (HTML/CSS/JS/React/GSAP)

The frontend must deliver a responsive, performant, and visually engaging experience.

* **REQ-F1 (State Management):** Manage complex client-side state to handle asynchronous data fetching and rapid UI updates without lagging.
* **REQ-F2 (Cinematic Rendering):** Implement high-performance data visualizations. Utilize libraries like D3.js for complex charts and React Three Fiber for the immersive sector breakdown visualization discussed in the design phase.
* **REQ-F3 (Scroll-Driven UX):** Integrate GSAP to trigger specific analytical insights (like historical drawdowns) based on scroll position, ensuring a progressive disclosure of complex data.
* **REQ-F4 (Form Validation):** Ensure robust client-side validation for the trade entry form (preventing negative quantities, validating PSX ticker formats, handling dates correctly).

### 3.3 UI/UX Design

The design team must translate financial data into an intuitive and premium interface.

* **REQ-D1 (Dark Mode Priority):** Given the nature of financial dashboards and the requirement for a "cinematic" feel, prioritize a high-contrast dark mode design system.
* **REQ-D2 (State Indication):** Design clear visual indicators differentiating when the PSX market is Open (09:32 - 15:30 PKT) versus Closed, and when data is actively refreshing.
* **REQ-D3 (Information Hierarchy):** Design the main dashboard to immediately present the top-level metrics (Total Value, Daily Change, Total P&L) before requiring the user to scroll for granular holdings data.

## 4. Key Constraints & Assumptions

* **Constraint 1:** The system relies on the open-source `psxdata` library. If the underlying PSX DPS endpoints change and the library breaks, the system will lose EOD updates until patched.
* **Assumption 1:** The user is tracking long-term holds and swing trades. High-frequency, sub-second latency is not required; therefore, polling or standard REST updates are sufficient over WebSockets.

---