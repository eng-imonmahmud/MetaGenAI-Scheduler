MetaGenAI-Scheduler 🤖📱
MetaGenAI-Scheduler is an intelligent, GUI-based desktop application written in Python that automates the generation and scheduling of social media content. Leveraging the power of the new Google Gemini API (google-genai), it automatically crafts tailored text descriptions and stunning visuals, then schedules them seamlessly to Facebook Pages and Instagram Business Accounts via the Meta Graph API.
Designed for digital marketers and content creators, it allows you to bulk-schedule a massive 270 posts across 30 days (9 posts per day at pre-defined hours) across 27 distinct US audience categories.

📊 System Architecture Diagram
[ User UI (Tkinter) ] 
        │
        ▼ (Reads Config & State)
[ Automation Core Engine ] ──► [ Local State Sync (JSON) ]
        │
        ├─► [ Gemini API ] ──► Generates Ad Text Copy
        ├─► [ Imagen API ] ──► Generates 1:1 Creative Images
        │        │
        │        └─► (If SDK Fails) ──► [ REST Fallback Layer ]
        ▼
[ Meta Graph API ] ──► Schedules to ──► [ FB Page & IG Business ]



✨ Key Features
Multi-Platform Automation: Schedules content simultaneously for both Facebook and Instagram.
Dual-Model Gemini Integration: Uses Gemini text models for high-converting copy and Imagen models for high-quality visuals.
Dynamic Model Fetching: Automatically fetches available text and image models based on your Gemini API key.
Smart Compliance & Guardrails: Automatically injects informational disclaimers for sensitive niches (Health, Finance, Legal, etc.) and filters out banned sales-pitch words (e.g., advice, guide, tips).
Fallback Robustness: Built-in REST API fallback mechanism for image generation if the SDK payload encounters hiccups.
State Persistence & Recovery: Local session saving (automation_state.json) lets you pause, resume, or recover progress seamlessly if interrupted.
Interactive GUI: Built with Python's Tkinter, offering progress bars, live logs, and intuitive controls.

🛠️ Tech Stack & Dependencies
Library / Tool
Purpose / Usage
google-genai (v1.0.0+)
Official Google SDK for text prompt processing and Imagen model image generation.
requests
Handles Meta Graph API POST requests and provides a REST API fallback for image generation.
Pillow (PIL)
Validates image formats and processes buffer objects.
tkinter & ttk
Renders the Graphical User Interface (GUI), progress bars, and logging screens.
threading
Manages heavy API calls in the background to prevent the main UI from freezing.
json & os
Handles local session tracking by writing and reading the automation_state.json file.


🚀 Installation & Setup
1. Clone the Repository
git clone https://github.com/YOUR_USERNAME/MetaGenAI-Scheduler.git
cd MetaGenAI-Scheduler


2. Install Dependencies
Make sure you have pip updated, then install the required Python packages:
pip install google-genai requests pillow


3. Meta API Configuration
Open the MetaGenAI-Scheduler.py file and replace the placeholder values at the top with your Meta Developer credentials:
# ==========================================
# CONFIGURATION & API KEYS
# ==========================================
FB_PAGE_ID = "YOUR_FACEBOOK_PAGE_ID" 
IG_ACCOUNT_ID = "YOUR_INSTAGRAM_BUSINESS_ACCOUNT_ID" 
META_ACCESS_TOKEN = "YOUR_META_LONG_LIVED_ACCESS_TOKEN" 


⚠️ Security Warning: Never commit your access tokens, page IDs, or API keys directly to public GitHub repositories. Use environment variables or keep them strictly local.

🎯 How To Use
Run the App: Execute python MetaGenAI-Scheduler.py from your terminal.
Authenticate Gemini: Input your Google Gemini API Key in the designated entry box and click "Fetch Models".
Select Models: Choose your preferred text model (e.g., gemini-2.5-pro) and image model (e.g., imagen-3.0) from the loaded dropdowns.
Set Start Date: Choose the date from which you want the 30-day scheduling calendar to kick off.
Control Center:
Click ▶ Start / Resume to begin the fully automated execution.
Click ⏸ Pause if you need to safely halt execution after the current running post.
Click ⏹ Reset Data to wipe out progress and reset the scheduler back to Post 1.

⚙️ Automated Scheduling Framework
The application splits the workflow into a systematic grid:
Total Posts: 270 Posts
Daily Frequency: 9 Posts/Day
Fixed Posting Hours (Local Time): 08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00, 21:00, 23:00.
Content Rotation: Loops sequentially through 27 lifestyle, professional, and corporate categories tailored for a US audience.

📌 Project Status
Completed. This project is fully functional and ready for deployment. There are no pending updates or feature additions planned.

🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the issues page if you want to contribute to code optimization or UI improvements.

📄 License
This project is licensed under the MIT License.
