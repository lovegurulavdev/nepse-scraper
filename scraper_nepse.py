import os
import time
from datetime import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from bs4 import BeautifulSoup
import chromedriver_autoinstaller

# Auto-install ChromeDriver
chromedriver_autoinstaller.install()

def setup_driver():
    """Configure Chrome driver for headless operation"""
    options = Options()
    options.headless = True
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.115 Safari/537.36')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(120)
    return driver

def search(driver, date):
    """Search for floorsheet by date"""
    try:
        driver.get("https://www.sharesansar.com/today-share-price")
        
        # Wait for date input field
        date_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//input[@id='fromdate']"))
        )
        time.sleep(2)
        
        # Clear and enter date
        date_input.clear()
        date_input.send_keys(date)
        time.sleep(1)
        
        # Click search button
        search_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@id='btn_todayshareprice_submit']"))
        )
        search_btn.click()
        time.sleep(3)
        
        # Check for no data message
        if driver.find_elements(By.XPATH, "//*[contains(text(), 'Could not find floorsheet matching the search criteria')]"):
            print(f"No data found for {date}")
            return False
            
        return True
        
    except TimeoutException:
        print(f"Timeout while searching for {date}")
        return False
    except Exception as e:
        print(f"Error in search: {e}")
        return False

def get_page_table(driver):
    """Extract table data from current page"""
    try:
        # Wait for table to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//table[@class='table table-bordered table-striped table-hover dataTable compact no-footer']"))
        )
        
        soup = BeautifulSoup(driver.page_source, 'lxml')
        table = soup.find("table", {"class": "table table-bordered table-striped table-hover dataTable compact no-footer"})
        
        if not table:
            return pd.DataFrame()
        
        tab_data = [[cell.text.replace('\r', '').replace('\n', '').strip() 
                    for cell in row.find_all(["th", "td"])]
                    for row in table.find_all("tr")]
        
        return pd.DataFrame(tab_data)
        
    except Exception as e:
        print(f"Error getting page table: {e}")
        return pd.DataFrame()

def scrape_data(driver, date):
    """Scrape all pages of data"""
    all_data = pd.DataFrame()
    page_num = 0
    
    while True:
        page_num += 1
        print(f"Scraping page {page_num}")
        
        # Get current page table
        page_df = get_page_table(driver)
        if not page_df.empty:
            all_data = pd.concat([all_data, page_df], ignore_index=True)
        
        # Try to go to next page
        try:
            next_btn = driver.find_element(By.LINK_TEXT, 'Next')
            # Check if next button is disabled
            if 'disabled' in next_btn.get_attribute('class'):
                break
            driver.execute_script("arguments[0].click();", next_btn)
            time.sleep(2)
        except NoSuchElementException:
            break
        except Exception:
            break
    
    return all_data

def clean_data(df):
    """Clean and format the scraped data"""
    if df.empty:
        return df
    
    # Remove duplicates
    df = df.drop_duplicates(keep='first')
    
    # Set first row as header
    if len(df) > 0:
        new_header = df.iloc[0]
        df = df[1:]
        df.columns = new_header
        
        # Remove S.No column if exists
        if 'S.No' in df.columns:
            df.drop(['S.No'], axis=1, inplace=True)
        
        # Convert numeric columns
        numeric_cols = ['Quantity', 'Rate', 'Amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].str.replace(',', ''), errors='coerce')
    
    return df

def save_data(df, date):
    """Save data to CSV file"""
    if df.empty:
        print(f"No data to save for {date}")
        return False
    
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # Format filename
    file_name = date.replace('/', '_')
    file_path = f"data/{file_name}.csv"
    
    # Save to CSV
    df.to_csv(file_path, index=False)
    print(f"Data saved to {file_path}")
    return True

def main():
    """Main execution function"""
    # Setup
    date = datetime.today().strftime('%m/%d/%Y')
    print(f"Starting scrape for date: {date}")
    
    # Initialize driver
    driver = setup_driver()
    
    try:
        # Search for date
        if not search(driver, date):
            print(f"No data found for {date}")
            driver.quit()
            return
        
        # Scrape all pages
        raw_data = scrape_data(driver, date)
        
        # Clean data
        cleaned_data = clean_data(raw_data)
        
        # Save data
        if not cleaned_data.empty:
            save_data(cleaned_data, date)
            print(f"Successfully scraped {len(cleaned_data)} records")
        else:
            print("No data to save")
            
    except Exception as e:
        print(f"Error in main execution: {e}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
