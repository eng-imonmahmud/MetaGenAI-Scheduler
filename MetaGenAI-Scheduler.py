import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
import json
import os
import io
import time
import datetime
import threading
from PIL import Image
from google import genai
from google.genai import types

# ==========================================
# CONFIGURATION & API KEYS
# ==========================================

FB_PAGE_ID = "PAGE ID" 
IG_ACCOUNT_ID = "IG ACCOUNT" 
META_ACCESS_TOKEN = "" 

CATEGORIES = [
    "US Automotive", "US Baby Care", "US Beauty", "US Beverage", "US Education", "US Electronics & Gadgets", "US Fashion", "US Food", "US Health", "US Home Appliances", "US Home Decor", 
    "US Home Improvement", "US Insurance", "US Kitchen", "US Laptop & Desktop", "US Lawn & Garden", "US Pet & Care", "US Recipe", "US Technology",
    "US Tips & Tricks", "US Toys", "US Travel", "US Laws", "US Tax", "US Finance", "US Career", "US Lifestyle"
]

SENSITIVE_CATEGORIES = ["US Health", "US Food", "US Baby Care", "US Insurance", "US Pet & Care", "US Laws", "US Tax", "US Finance", "US Career"]
DISCLAIMER = "\n\nDisclaimer: This content is for informational purposes only and does not constitute professional, legal, medical, or financial instruction."
BANNED_WORDS = ['advice', 'advices', 'tips', 'guide', 'adviser', 'advisor']

STATE_FILE = "automation_state.json"
TOTAL_POSTS = 270
POSTS_PER_DAY = 9
POST_HOURS = [8, 10, 12, 14, 16, 18, 20, 21, 23]

# ==========================================
# IMAGE GENERATION CLASS
# ==========================================
class ImageGenerator:
    def __init__(self, api_key, model_name):
        self.api_key = api_key
        self.model_name = model_name
        self.clean_model = model_name.replace('models/', '')
        self.client = genai.Client(api_key=self.api_key)
        self.http_session = requests.Session()

    def verify_image(self, image_bytes):
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.load()  
            return True
        except Exception:
            return False

    def generate(self, prompt):
        image_bytes = None
        try:
            if "imagen" in self.clean_model.lower():
                result = self.client.models.generate_images(
                    model=self.model_name,
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        output_mime_type="image/jpeg",
                        aspect_ratio="1:1"
                    )
                )
                if result.generated_images:
                    image_bytes = result.generated_images[0].image.image_bytes
            else:
                result = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                if result.candidates:
                    for candidate in result.candidates:
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            for part in candidate.content.parts:
                                if hasattr(part, 'inline_data') and part.inline_data:
                                    image_bytes = part.inline_data.data
                                    break
                        if image_bytes:
                            break
            
            if image_bytes and self.verify_image(image_bytes):
                return image_bytes
            else:
                raise ValueError("SDK did not return a valid image payload.")
                
        except Exception as e:
            print(f"SDK Generation failed: {e}. Attempting REST Fallback...")
            return self._generate_rest(prompt)

    def _generate_rest(self, prompt):
        headers = {"Content-Type": "application/json"}
        b64_img = None
        try:
            if "imagen" in self.clean_model.lower():
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.clean_model}:predict?key={self.api_key}"
                payload = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1}}
                response = self.http_session.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                if 'predictions' in data and data['predictions']:
                    b64_img = data['predictions'][0].get('bytesBase64Encoded')
            else:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.clean_model}:generateContent?key={self.api_key}"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                response = self.http_session.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                if 'candidates' in data:
                    for candidate in data.get('candidates', []):
                        for part in candidate.get('content', {}).get('parts', []):
                            if 'inlineData' in part:
                                b64_img = part['inlineData'].get('data')
                                break
                        if b64_img:
                            break

            if not b64_img:
                raise ValueError("REST API Response contained no valid image payload.")

            import base64
            image_bytes = base64.b64decode(b64_img)
            if self.verify_image(image_bytes):
                return image_bytes
            else:
                raise ValueError("REST API returned a corrupted image.")
        except Exception as e:
            raise ValueError(f"REST Fallback Error: {e}")

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def schedule_facebook_post(page_id, token, text, image_path, timestamp):
    url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
    payload = {'message': text, 'published': 'false', 'scheduled_publish_time': str(timestamp), 'access_token': token}
    with open(image_path, 'rb') as f:
        files = {'source': f}
        response = requests.post(url, data=payload, files=files)
    if response.status_code != 200:
        raise Exception(f"Facebook Schedule Error: {json.dumps(response.json())}")
    return response.json()

# ==========================================
# GUI AND MAIN APPLICATION LOGIC
# ==========================================
class SocialAutomationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MetaGenAI-Scheduler")
        self.root.geometry("750x780") 
        
        # Application State
        self.posts_completed = 0
        self.is_paused = False
        
        # Setup UI
        self._build_ui()
        self.load_state() # Load saved progress on startup

    def _build_ui(self):
        # API Frame
        frame_api = ttk.Frame(self.root)
        frame_api.pack(pady=10, fill=tk.X, padx=20)
        ttk.Label(frame_api, text="Gemini API Key:").pack(side=tk.LEFT, padx=5)
        self.api_entry = ttk.Entry(frame_api, width=40, show="*")
        self.api_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_api, text="Fetch Models", command=self.fetch_models_thread).pack(side=tk.LEFT, padx=5)

        # Models Frame
        frame_models = ttk.Frame(self.root)
        frame_models.pack(pady=10, fill=tk.X, padx=20)
        ttk.Label(frame_models, text="Text Model:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.text_model_combo = ttk.Combobox(frame_models, width=35, state="readonly")
        self.text_model_combo.grid(row=0, column=1, padx=10, pady=5)
        ttk.Label(frame_models, text="Image Model:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.img_model_combo = ttk.Combobox(frame_models, width=35, state="readonly")
        self.img_model_combo.grid(row=1, column=1, padx=10, pady=5)

        # Date Frame
        frame_auto = ttk.Frame(self.root)
        frame_auto.pack(pady=10)
        ttk.Label(frame_auto, text="Start Date (YYYY-MM-DD):").pack(side=tk.LEFT, padx=5)
        self.date_entry = ttk.Entry(frame_auto, width=15)
        self.date_entry.insert(0, datetime.datetime.now().strftime("%Y-%m-%d"))
        self.date_entry.pack(side=tk.LEFT, padx=5)

        # Progress and Counters Frame
        frame_status = ttk.Frame(self.root)
        frame_status.pack(pady=10, fill=tk.X, padx=30)
        self.progress_label = ttk.Label(frame_status, text="Day Progress: 0 / 30", font=("Arial", 10, "bold"))
        self.progress_label.pack(side=tk.LEFT, padx=5)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(frame_status, variable=self.progress_var, maximum=30, length=250)
        self.progress_bar.pack(side=tk.LEFT, padx=10)
        self.counter_label = ttk.Label(frame_status, text="Total Posts: 0 / 270", font=("Arial", 10, "bold"), foreground="blue")
        self.counter_label.pack(side=tk.RIGHT, padx=5)

        # Control Buttons Frame
        frame_controls = ttk.Frame(self.root)
        frame_controls.pack(pady=10, fill=tk.X, padx=50)
        
        self.btn_start = ttk.Button(frame_controls, text="▶ Start / Resume", command=self.start_generation, state=tk.DISABLED)
        self.btn_start.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        self.btn_pause = ttk.Button(frame_controls, text="⏸ Pause", command=self.pause_generation, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        
        self.btn_reset = ttk.Button(frame_controls, text="⏹ Reset Data", command=self.reset_data)
        self.btn_reset.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        # Log Area
        self.log_area = scrolledtext.ScrolledText(self.root, height=15, width=85, state='disabled')
        self.log_area.pack(pady=10, padx=10)

    # ---------------- STATE MANAGEMENT ----------------
    def save_state(self):
        state = {
            'posts_completed': self.posts_completed,
            'start_date': self.date_entry.get().strip()
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                    self.posts_completed = state.get('posts_completed', 0)
                    saved_date = state.get('start_date', '')
                    if saved_date:
                        self.date_entry.delete(0, tk.END)
                        self.date_entry.insert(0, saved_date)
                    
                    if self.posts_completed > 0:
                        self.log(f"Previous session found. Resuming from Post: {self.posts_completed} / 270")
            except Exception as e:
                self.log(f"Error loading state: {e}")
        self.update_ui_status()

    def reset_data(self):
        if messagebox.askyesno("Confirm Reset", "Are you sure you want to completely reset the progress? It will start from Post 1."):
            self.posts_completed = 0
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
            self.update_ui_status()
            self.log("Data cleared. Progress reset to 0.")

    def update_ui_status(self):
        current_day = (self.posts_completed // POSTS_PER_DAY)
        if self.posts_completed % POSTS_PER_DAY > 0 or self.posts_completed == TOTAL_POSTS:
            current_day += 1
            
        def update():
            self.progress_label.config(text=f"Day Progress: {min(current_day, 30)} / 30")
            self.progress_var.set(min(current_day, 30))
            self.counter_label.config(text=f"Total Posts: {self.posts_completed} / 270")
        self.root.after(0, update)

    # ---------------- LOGGING & UI THREADING ----------------
    def log(self, message):
        def append():
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}\n")
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
        self.root.after(0, append)

    def fetch_models_thread(self):
        threading.Thread(target=self.fetch_models, daemon=True).start()

    def fetch_models(self):
        api_key = self.api_entry.get().strip()
        if not api_key:
            messagebox.showerror("Error", "Please enter Gemini API Key")
            return
            
        self.log("Fetching available models from Gemini API...")
        try:
            client = genai.Client(api_key=api_key)
            models_iterator = client.models.list()
            model_names = [m.name for m in models_iterator]
            
            if not model_names:
                self.log("No models found for this API Key.")
                return

            def update_ui():
                self.text_model_combo['values'] = model_names
                self.img_model_combo['values'] = model_names
                default_text = next((m for m in model_names if 'gemini-2.5-pro' in m), model_names[0])
                default_img = next((m for m in model_names if 'imagen-3.0' in m), model_names[0])
                self.text_model_combo.set(default_text)
                self.img_model_combo.set(default_img)
                self.btn_start.config(state=tk.NORMAL)
                self.log(f"Successfully loaded models. Ready to start.")

            self.root.after(0, update_ui)
        except Exception as e:
            self.log(f"Failed to fetch models: {e}")

    # ---------------- CORE AUTOMATION LOGIC ----------------
    def start_generation(self):
        start_date = self.date_entry.get()
        api_key = self.api_entry.get().strip()
        text_model = self.text_model_combo.get()
        img_model = self.img_model_combo.get()
        
        if not api_key or not text_model or not img_model:
            messagebox.showerror("Error", "Missing API Key or Model selection.")
            return

        if self.posts_completed >= TOTAL_POSTS:
            messagebox.showinfo("Complete", "All 270 posts have already been scheduled. Please click 'Reset Data' to start over.")
            return

        self.is_paused = False
        self.btn_start.config(state=tk.DISABLED)
        self.btn_reset.config(state=tk.DISABLED)
        self.btn_pause.config(state=tk.NORMAL)

        threading.Thread(target=self.generate_workflow, args=(api_key, text_model, img_model, start_date), daemon=True).start()

    def pause_generation(self):
        self.is_paused = True
        self.btn_pause.config(state=tk.DISABLED)
        self.log("⚠️ Pause requested. Waiting for current post to finish...")

    def reset_ui_buttons(self):
        self.btn_start.config(state=tk.NORMAL)
        self.btn_reset.config(state=tk.NORMAL)
        self.btn_pause.config(state=tk.DISABLED)

    def generate_workflow(self, api_key, text_model, img_model, start_date):
        self.log(f"--- Starting/Resuming 30-Days FB & IG Automation ---")
        
        try:
            client = genai.Client(api_key=api_key)
            img_generator = ImageGenerator(api_key=api_key, model_name=img_model)
            base_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")

            while self.posts_completed < TOTAL_POSTS:
                # 🛑 Pause Check
                if self.is_paused:
                    self.log("⏸ Automation paused successfully. State saved.")
                    self.save_state()
                    self.root.after(0, self.reset_ui_buttons)
                    return # Exit the thread
                
                # Calculate Day and Post Time mathematically
                current_day_index = self.posts_completed // POSTS_PER_DAY
                post_index_in_day = self.posts_completed % POSTS_PER_DAY
                
                current_date = base_date + datetime.timedelta(days=current_day_index)
                post_time = current_date.replace(hour=POST_HOURS[post_index_in_day], minute=0)
                timestamp = int(post_time.timestamp())

                # Calculate Category
                category = CATEGORIES[self.posts_completed % len(CATEGORIES)]
                
                self.log(f"\n-> Processing Post {self.posts_completed + 1}/270 | Day {current_day_index + 1} | Category: {category}")
                
                # 1. TEXT GENERATION
                prompt = f"""
                Write a social media post about {category} targeting a US Audience.
                STRICT RULES: Do not use the words: {', '.join(BANNED_WORDS)}. Do not give direct advice.
                Return ONLY a valid JSON object with the following keys exactly:
                "facebook_post", "instagram_caption", "image_generation_prompt".
                """
                
                response = client.models.generate_content(
                    model=text_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                
                content = json.loads(response.text)
                if category in SENSITIVE_CATEGORIES:
                    content['facebook_post'] += DISCLAIMER
                    content['instagram_caption'] += DISCLAIMER
                
                # 2. IMAGE GENERATION
                image_bytes = None
                max_retries = 5
                for attempt in range(1, max_retries + 1):
                    try:
                        self.log(f"Generating Image (Attempt {attempt}/{max_retries})...")
                        image_bytes = img_generator.generate(content['image_generation_prompt'])
                        break 
                    except Exception as img_err:
                        self.log(f"Image Error: {img_err}")
                        if attempt < max_retries: time.sleep(5)
                        else:
                            self.log("❌ CRITICAL ERROR: Failed to generate image after 5 attempts.")
                            self.root.after(0, self.reset_ui_buttons)
                            return 

                if not image_bytes: return 

                # Save locally
                image_filename = f"local_img_{int(time.time())}.jpg"
                try:
                    pil_img = Image.open(io.BytesIO(image_bytes))
                    if pil_img.mode != "RGB":
                        pil_img = pil_img.convert("RGB")
                    pil_img.save(image_filename, format="JPEG", quality=95)
                    pil_img.close()  
                except Exception as save_err:
                    self.log(f"Error saving image: {save_err}")
                    self.root.after(0, self.reset_ui_buttons)
                    return
                
                # 3. META SCHEDULING (FACEBOOK)
                fb_cdn_url = ""
                try:
                    self.log(f"Scheduling FB Post for {post_time.strftime('%Y-%m-%d %H:%M:%S')}...")
                    fb_res = schedule_facebook_post(FB_PAGE_ID, META_ACCESS_TOKEN, content['facebook_post'], image_filename, timestamp)
                    self.log("Facebook Scheduling Complete.")
                    
                    fb_photo_id = fb_res.get('id')
                    if fb_photo_id:
                        self.log("Extracting Facebook's CDN link for Instagram...")
                        info_res = requests.get(f"https://graph.facebook.com/v19.0/{fb_photo_id}?fields=images&access_token={META_ACCESS_TOKEN}")
                        if info_res.status_code == 200:
                            fb_cdn_url = info_res.json().get('images', [{}])[0].get('source', '')
                except Exception as meta_err:
                    self.log(f"Facebook scheduling error: {meta_err}")

                # 4. INSTAGRAM POSTING
                if fb_cdn_url:
                    try:
                        self.log(f"Scheduling Instagram Post for {post_time.strftime('%Y-%m-%d %H:%M:%S')}...")
                        
                        # Step 1: Create Media Container
                        ig_media_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media"
                        ig_payload = {
                            'image_url': fb_cdn_url.strip(), 
                            'caption': content['instagram_caption'], 
                            'access_token': META_ACCESS_TOKEN
                        }
                        res_media = requests.post(ig_media_url, params=ig_payload)
                        if res_media.status_code != 200: raise Exception(res_media.text)
                        
                        creation_id = res_media.json().get('id')
                        
                        # Step 2: Publish the Container (with Schedule Parameters)
                        ig_publish_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media_publish"
                        pub_payload = {
                            'creation_id': creation_id, 
                            'access_token': META_ACCESS_TOKEN,
                            'published': 'false', # Tells Meta not to publish immediately
                            'scheduled_publish_time': str(timestamp) # Tells Meta when to publish
                        }
                        res_pub = requests.post(ig_publish_url, params=pub_payload)
                        if res_pub.status_code != 200: raise Exception(res_pub.text)
                        
                        self.log("Instagram Post Scheduled Successfully! 🎉")
                    except Exception as ig_err:
                        self.log(f"Instagram Post Failed: {ig_err}")
                else:
                    self.log("Could not extract Facebook CDN link. Skipping IG.")
                
                # Cleanup Image
                try:
                    if os.path.exists(image_filename):
                        os.remove(image_filename)
                        self.log("Local image deleted successfully.")
                except Exception as e:
                    pass
                
                # Update State and UI
                self.posts_completed += 1
                self.save_state() # Save progress locally
                self.update_ui_status()
                self.log(f"--- Finished Post {self.posts_completed} ---\n")
                
                # Safety Sleep before next post (unless paused or finished)
                if self.posts_completed < TOTAL_POSTS and not self.is_paused:
                    time.sleep(3)

            # Done Loop Condition Check
            if self.posts_completed >= TOTAL_POSTS:
                self.log("=== Automation Complete! 30 Days Scheduled. ===")
                self.update_ui_status()
                self.root.after(0, self.reset_ui_buttons)
                self.root.after(0, lambda: messagebox.showinfo("Success", "All 270 Posts completely scheduled!"))

        except Exception as e:
            self.log(f"Fatal Error: {e}")
            self.root.after(0, self.reset_ui_buttons)

if __name__ == "__main__":
    root = tk.Tk()
    app = SocialAutomationApp(root)
    root.mainloop()