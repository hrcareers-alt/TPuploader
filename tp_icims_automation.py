import os
import re
import time
import random
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

from tp_locations import resolve_tp_site

load_dotenv()

# --- CONFIGURATION ---
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
SHEET_URL_1 = "https://docs.google.com/spreadsheets/d/1NoRX955F0dpxMReiC-6lcd3hgxFDccS3H9hzabTQghE/edit"
SHEET_URL_2 = "https://docs.google.com/spreadsheets/d/1PYPebwsRPiO8y7ogsMegRpSFmR3E84gGPnJohcjm04o/edit"

LINK_VISMIN = "https://careersph-teleperformance.icims.com/jobs/52133/teleperformance-philippines---vismin---customer-expert/job?mode=view"
LINK_LUZON = "https://careersph-teleperformance.icims.com/jobs/52132/teleperformance-philippines---luzon---customer-expert/candidate?from=login&eem=vRzBjhgEMAHCL76SQNoTqpnZVGKyFVjneZ06kKC7Fwl5LgpU6L0tNlWGFutUcmK5&code=913a1a28229a2f6b2f39b76a44d492b1af96b5de85512cf0cf1c0c3a4c009b1a&ga=9173206f7729b4756a56ce41aec0687b33c4e4bb5009d62dc2137e4f9a39c2b4&accept_gdpr=1"

# --- ANTI-CAPTCHA HELPERS ---
def human_delay(min_ms=1000, max_ms=3000):
    time.sleep(random.uniform(min_ms, max_ms) / 1000.0)

def human_type(locator, text):
    locator.type(text, delay=random.randint(50, 150))
    human_delay(500, 1000)

# --- LOGIC HELPERS ---
def get_region_link(location):
    if resolve_tp_site(location) == "vismin":
        return LINK_VISMIN
    return LINK_LUZON

def setup_gspread():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    return gspread.authorize(creds)

def process_tp_candidates():
    gc = setup_gspread()
    doc = gc.open_by_url(SHEET_URL_1)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        tabs_to_process = ["MODERN TRACTION", "JOBSTREET", "VALID CONSENT - TP, FVR & EXL"]
        
        for tab_name in tabs_to_process:
            try:
                ws = doc.worksheet(tab_name)
            except gspread.exceptions.WorksheetNotFound:
                continue
                
            data = ws.get_all_values()
            if not data: continue
            
            headers = [h.strip() for h in data[0]]
            
            tp_col = next((i for i, h in enumerate(headers) if "TP" in h.upper()), None)
            pref_col = next((i for i, h in enumerate(headers) if "PREFERRED" in h.upper() or "ENDORSE" in h.upper()), None)
            
            if tp_col is None or pref_col is None:
                continue
                
            for row_idx, row in enumerate(data[1:], start=2):
                if len(row) <= tp_col:
                    row.extend([""] * (tp_col - len(row) + 1))
                
                tp_remark = row[tp_col].strip()
                if tp_remark:
                    continue
                
                pref_val = row[pref_col].strip().upper()
                if "TELEPERFORMANCE" not in pref_val and "ALL OF THE ABOVE" not in pref_val:
                    ws.update_cell(row_idx, tp_col + 1, "EXECUTIVE TEAM / N")
                    continue
                
                first_name = row[headers.index("First Name")] if "First Name" in headers else ""
                last_name = row[headers.index("Last Name")] if "Last Name" in headers else ""
                email = row[headers.index("Email Address")] if "Email Address" in headers else row[5]
                phone = row[headers.index("Mobile Number")] if "Mobile Number" in headers else row[4]
                location = row[headers.index("Location") if "Location" in headers else headers.index("City")] 
                education = row[headers.index("Highest Educational")] if "Highest Educational" in headers else ""
                
                # Setup Character Reference Data
                cr_name_idx = next((i for i, h in enumerate(headers) if "CHARACTER REF" in h.upper() and "NAME" in h.upper()), None)
                cr_email_idx = next((i for i, h in enumerate(headers) if "CHARACTER REF" in h.upper() and "EMAIL" in h.upper()), None)
                cr_phone_idx = next((i for i, h in enumerate(headers) if "CHARACTER REF" in h.upper() and ("NUMBER" in h.upper() or "CONTACT" in h.upper() or "PHONE" in h.upper())), None)

                cr_name_raw = row[cr_name_idx].strip() if cr_name_idx is not None and len(row) > cr_name_idx else ""
                cr_email_raw = row[cr_email_idx].strip() if cr_email_idx is not None and len(row) > cr_email_idx else ""
                cr_phone_raw = row[cr_phone_idx].strip() if cr_phone_idx is not None and len(row) > cr_phone_idx else ""

                # Fallback Logic for Character References
                cr_first = cr_name_raw.split()[0] if cr_name_raw else first_name
                cr_last = " ".join(cr_name_raw.split()[1:]) if len(cr_name_raw.split()) > 1 else (last_name if not cr_name_raw else "")
                cr_email = cr_email_raw if cr_email_raw else email
                cr_phone = cr_phone_raw if cr_phone_raw else phone

                job_link = get_region_link(location)
                page = context.new_page()
                stealth_sync(page)
                
                try:
                    page.goto(job_link)
                    human_delay(2000, 4000)
                    
                    frame = page.frame_locator("iframe#icims_content_iframe")
                    
                    apply_btn = frame.locator("a[title*='Apply for this Job']").first
                    apply_btn.click()
                    human_delay(3000, 5000)
                    
                    email_input = frame.locator("input[name='email']")
                    human_type(email_input, email)
                    
                    frame.locator("input#cb_gdpr_consent").check()
                    human_delay(500, 1500)
                    frame.locator("input#enterEmailSubmitButton").click()
                    
                    human_delay(4000, 7000)
                    
                    if frame.locator("input[name='password']").count() > 0 and frame.locator("input#loginSubmitButton").count() > 0:
                        ws.update_cell(row_idx, tp_col + 1, "EXECUTIVE TEAM / E")
                        page.close()
                        continue
                    
                    human_type(frame.locator("input[name='password']"), "Job_offer#247")
                    human_type(frame.locator("input[name='password_verify']"), "Job_offer#247")
                    
                    human_type(frame.locator("input[name='firstname']"), first_name)
                    human_type(frame.locator("input[name='lastname']"), last_name)
                    
                    frame.locator("select[name='phone_type']").select_option(label="Mobile")
                    human_type(frame.locator("input[name='phone_number']"), phone)
                    frame.locator("input[name='text_messages_consent'][value='Yes']").check()
                    
                    frame.locator("select[name='how_did_you_hear']").select_option(label="Agencies")
                    human_delay(1000, 2000)
                    human_type(frame.locator("input[name='how_did_you_hear_specify']"), "Edward Belacse Career Consultancy Services")
                    
                    frame.locator("select[name='address_type']").select_option(label="Physical")
                    frame.locator("select[name='country']").select_option(label="Philippines")
                    human_type(frame.locator("input[name='address']"), location)
                    human_type(frame.locator("input[name='city']"), location)
                    human_type(frame.locator("input[name='state']"), location)
                    
                    human_type(frame.locator("input[name='emergency_contact_name']"), f"{first_name} {last_name}")
                    human_type(frame.locator("input[name='emergency_contact_phone']"), phone)
                    human_type(frame.locator("input[name='emergency_contact_secondary_phone']"), phone)
                    human_type(frame.locator("input[name='emergency_contact_email']"), email)
                    human_type(frame.locator("input[name='emergency_contact_postal_code']"), "1000")
                    human_type(frame.locator("input[name='emergency_contact_state']"), location)
                    human_type(frame.locator("input[name='emergency_contact_city']"), location)
                    frame.locator("select[name='emergency_contact_country']").select_option(label="Philippines")
                    human_type(frame.locator("input[name='emergency_contact_address1']"), location)
                    human_type(frame.locator("input[name='emergency_contact_address2']"), location)
                    
                    frame.locator("select[name='degree']").select_option(label=education)
                    human_type(frame.locator("input[name='major']"), "N/A")
                    human_type(frame.locator("input[name='school']"), education)
                    frame.locator("select[name='finished_school']").select_option(label="Yes")
                    
                    frame.locator("input[value='Submit Profile']").click()
                    human_delay(4000, 6000)
                    
                    frame.locator("input[name='q_18_years'][value='Yes']").check()
                    frame.locator("input[name='q_amenable_wah'][value='Yes']").check()
                    frame.locator("input[name='q_employed_tp'][value='No']").check()
                    frame.locator("input[name='q_filled_app_tp'][value='No']").check()
                    frame.locator("input[name='q_laptop_desktop'][value='Yes']").check()
                    human_type(frame.locator("input[name='q_download_speed']"), "100")
                    human_type(frame.locator("input[name='q_upload_speed']"), "100")
                    frame.locator("input[name='q_currently_enrolled'][value='No']").check()
                    
                    frame.locator("select[name='q_prefer_site']").select_option(index=1)
                    frame.locator("select[name='q_best_time_call']").select_option(label="Anytime")
                    frame.locator("select[name='q_other_contact']").select_option(label="Others")
                    human_type(frame.locator("input[name='q_other_contact_info']"), phone)
                    
                    human_type(frame.locator("input[name='q_referrer_ident']"), "Edward Belacse Career Consultancy Services")
                    human_type(frame.locator("input[name='q_referrer_name']"), "Edward Belacse Career Consultancy Services")
                    
                    frame.locator("input[name='q_nbi_clearance'][value='Yes']").check()
                    frame.locator("select[name='q_work_setup']").select_option(label="both")
                    frame.locator("input[name='q_shifting_schedule'][value='yes']").check()
                    frame.locator("input[name='q_weekends_holidays'][value='yes']").check()
                    human_type(frame.locator("input[name='q_expected_salary']"), "21000")
                    frame.locator("select[name='q_start_working']").select_option(label="ASAP")
                    
                    # Applied Character Reference Fallback Logic
                    human_type(frame.locator("input[name='ref_first_name']"), cr_first)
                    human_type(frame.locator("input[name='ref_last_name']"), cr_last)
                    human_type(frame.locator("input[name='ref_email']"), cr_email)
                    human_type(frame.locator("input[name='ref_phone']"), cr_phone)
                    human_type(frame.locator("input[name='ref_company']"), "N/A")
                    
                    frame.locator("input#signature_checkbox").check()
                    frame.locator("input[value='Save & Return Later']").click()
                    human_delay(3000, 5000)
                    
                    ws.update_cell(row_idx, tp_col + 1, "EXECUTIVE TEAM / Y")
                    
                except Exception as e:
                    print(f"Error on row {row_idx}: {e}")
                finally:
                    page.close()

        browser.close()

if __name__ == "__main__":
    process_tp_candidates()
