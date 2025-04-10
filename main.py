
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import requests, json, base64, os
from bs4 import BeautifulSoup

app = FastAPI(
    title="Image Search & Upload API",
    description="Search for an image from Bing and upload to imgbb. Returns a markdown URL."
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def plugin_manifest():
    return FileResponse("static/ai-plugin.json")

def is_supported_image_format(content_type):
    return any(fmt in content_type for fmt in ["jpeg", "jpg", "png"])

def search_image_url(query):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.bing.com/"
    }
    res = requests.get(f"https://www.bing.com/images/search?q={query}", headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    items = soup.find_all("a", class_="iusc")
    for item in items:
        try:
            metadata = json.loads(item.get("m"))
            image_url = metadata.get("murl")
            if image_url:
                head_res = requests.head(image_url, timeout=5)
                content_type = head_res.headers.get("Content-Type", "")
                if head_res.status_code == 200 and is_supported_image_format(content_type):
                    return image_url
        except Exception:
            continue
    raise Exception("No supported image found (jpeg/jpg/png only).")

def download_image(image_url):
    res = requests.get(image_url, stream=True, timeout=10)
    if res.status_code == 200 and res.headers.get("Content-Type", "").startswith("image"):
        return res.content
    raise Exception("Failed to download image.")

def upload_to_imgbb(image_bytes, imgbb_api_key):
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {"key": imgbb_api_key, "image": image_base64}
    res = requests.post("https://api.imgbb.com/1/upload", data=payload)
    json_data = res.json()
    if res.status_code == 200 and json_data.get("success") == True:
        return json_data["data"]["url"]
    raise Exception("Failed to upload to imgbb.")

@app.get("/get_image_url")
def get_image_url(
    product: str = Query(..., description="Search keyword"),
    imgbb_key: str = Query(..., description="Your imgbb API key")
):
    try:
        image_url = search_image_url(product)
        image_bytes = download_image(image_url)
        final_url = upload_to_imgbb(image_bytes, imgbb_key)
        return JSONResponse(content={
            "status": "success",
            "product": product,
            "url": final_url,
            "markdown_embed": f"![{product}]({final_url})"
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
