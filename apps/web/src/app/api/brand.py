from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Simple hardcoded brand registry as an example
BRAND_REGISTRY = {
    "ExampleBrand": True,
    "TestBrand": False,
    "TrustedCompany": True
}

class BrandVerificationResult(BaseModel):
    brand: str
    verified: bool

@router.get("/brand/{brand_name}", response_model=BrandVerificationResult)
async def verify_brand(brand_name: str):
    verified = BRAND_REGISTRY.get(brand_name)

    if verified is None:
        raise HTTPException(status_code=404, detail="Brand not found.")
    return BrandVerificationResult(brand=brand_name, verified=verified)