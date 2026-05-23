# Automated Online Assessment Testing Framework

A robust, enterprise-grade Automated Testing and Interaction Framework designed to validate user flows, page transitions, and interactive elements on dynamic web-based online assessment platforms. 

Using Selenium WebDriver (Python) paired with a clean architectural design, the framework automates complex candidate testing tasks such as dynamic multi-factor OTP retrieval, candidate credential verification, structural assessment scanning, and complex answer input validation (MCQ and C++ Coding environments) with a self-healing LLM feedback loop.

---

## 🛠 Core Architectural Pattern: Page Object Model (POM)

This codebase strictly adheres to the **Page Object Model (POM)** architectural pattern. 

* **Encapsulation**: Each webpage or structural component is represented by its own Python class.
* **Separation of Concerns**: Locators (XPaths, CSS selectors) and action methods are contained entirely within their respective Page classes. The orchestrator script (`main.py`) only interacts with the page classes via clean API methods.
* **Maintainability**: If the platform's UI layout or styling changes, only the selectors in the specific page class file need to be updated, leaving the main execution flow completely untouched.

---

## 📂 Directory & File Structure

```
TestCase1/
├── config/
│   └── settings.py          # Environment configurations, URLs, user profiles, and timeouts.
├── pages/
│   ├── base_page.py         # Base Page wrapper class containing driver context and base helpers.
│   ├── instructions_page.py # Accepts assessment declarations and accepts rules.
│   ├── login_page.py        # Automates candidate login and Multi-Factor OTP verification.
│   ├── candidate_details.py # Fills candidate details (Name, Roll Number, Mobile).
│   ├── start_test_page.py   # Handles start test initiation.
│   ├── summary_page.py      # Scans structural layout, section counts, and builds summary files.
│   └── question_page.py     # Answering engine. Handles MCQ selection and Code injection.
├── utils/
│   ├── driver_factory.py    # Thread-safe WebDriver initialization.
│   ├── llm_solver.py        # Solver broker using generative AI with IPC bridge fallback.
│   ├── otp_fetcher.py       # Scrapes and fetches verification codes from Yopmail via multi-tab context.
│   ├── selenium_helpers.py  # Wrapper layer for safe clicks, waits, scrolls, and screenshots.
│   └── logger.py            # Stream and file logger context.
├── requirements.txt         # Project dependencies.
├── main.py                  # Main orchestrator script.
└── README.md                # Project documentation.
```

---

## 🚀 Key Technical Capabilities

### ⚡ Multi-Tab Dynamic OTP Fetching
Instead of using mock OTPs, the framework programmatically manages a secondary browser tab, navigates to a temporary email service (Yopmail), scrapes the dynamic one-time authentication code in real-time, switches back to the primary workspace, and continues the authentication flow.

### 🎯 Dynamic MCQ Option Selection Algorithm
To prevent failures from dynamic or randomized element IDs, a resilient matching engine is used:
* Evaluates five diverse XPath patterns mapping relative siblings, label parents, and ancestors.
* Falls back to a DOM-tree text-proximity scan to locate input controls relative to their surrounding option text.

### 💻 Developer Editor Code Injection (Monaco / CodeMirror)
Online assessments leverage professional code editors. Standard text key inputs are slow and prone to timing errors. This framework:
1. Performs direct JS value injection via internal editor APIs (Monaco/CodeMirror).
2. Falls back to an OS-independent clipboard-injection and focus-trigger key sequencing flow if APIs are locked down.

### 🔄 Dynamic Self-Healing Solver Loop
An automated loop validates coding solutions:
* Click **"Run"** to execute code against sample test cases.
* If compile or runtime errors are found, the framework extracts the exact traceback from the panel and sends it back to the solver along with the failing code to self-heal and rewrite it correctly.
* Submits via **"Submit"** only after ensuring the code compiles and passes successfully.

---

## 🏁 Getting Started

### 1. Install Dependencies
Ensure you have Python 3.8+ installed, then run:
```bash
pip install -r requirements.txt
```

### 2. Configure Settings
Configure your user details, NVIDIA API Key, and target URLs in `config/settings.py`.

### 3. Run the Automation
Start the automation runner:
```bash
python main.py
```

---

## 📊 Summary Outputs
Upon scanning the overall assessment structure, the framework automatically generates two downloadable reports:
* **HTML Summary Table**: A clean, highly presentable tabular overview of all sections, section numbers, question counts, and exact question descriptions (`assessment_summary.html`).
* **Text Summary Report**: A standard plaintext representation for backwards-compatible logging (`assessment_summary.txt`).
