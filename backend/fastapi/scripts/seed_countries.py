from app.db.session import SessionLocal
from app.models.location_config import Country, Currency, EmergencyNumber, PaymentMethodConfig


COUNTRIES = [
    ("Togo", "Lome"),
    ("Benin", "Cotonou"),
    ("Ghana", "Accra"),
    ("Estonia", "Tallinn"),
    ("Portugal", "Lisbon"),
    ("France", "Paris"),
]


def run_seed():
    db = SessionLocal()
    try:
        for country_name, city in COUNTRIES:
            country = db.query(Country).filter(Country.name == country_name).one_or_none()
            if country is None:
                country = Country(name=country_name, city=city)
                db.add(country)
                db.flush()
                db.add(PaymentMethodConfig(country_id=country.id, method_name="CARD"))
                db.add(PaymentMethodConfig(country_id=country.id, method_name="MOBILE_MONEY"))
                db.add(EmergencyNumber(country_id=country.id, service_name="POLICE", phone_number="112"))
        if db.query(Currency).filter(Currency.code == "EUR").one_or_none() is None:
            db.add(Currency(code="EUR", name="Euro"))
        if db.query(Currency).filter(Currency.code == "XOF").one_or_none() is None:
            db.add(Currency(code="XOF", name="West African CFA franc"))
        if db.query(Currency).filter(Currency.code == "GHS").one_or_none() is None:
            db.add(Currency(code="GHS", name="Ghanaian Cedi"))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
