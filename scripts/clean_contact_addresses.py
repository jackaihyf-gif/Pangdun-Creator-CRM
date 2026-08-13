"""Move reviewed shipping addresses out of contact notes.

Run without ``--apply`` for a plan. The script is intentionally bound to
reviewed contact IDs from the 2026-08-13 audit and is safe to rerun: imported
addresses are keyed by their original source note plus a stable source suffix.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from backend.app.database import SessionLocal
from backend.app.models import AuditLog, Contact, Media, ShippingAddress, User


ADDRESSES: dict[int, list[dict]] = {
    5: [{"recipient_name": "Ahmed Erum Rasheed", "address_text": "36 Lindley Rd, Bradford BD5 7PD, UK", "postal_code": "BD5 7PD", "country": "英国"}],
    6: [{"recipient_name": "ARX ID Media", "address_text": "PT Berlian Cahaya Teknologi, Jl. Kenjeran No.151, Kapasmadya Baru, Kec. Tambaksari, Kota Surabaya, Jawa Timur 60137", "city": "Surabaya", "region": "Jawa Timur", "postal_code": "60137", "country": "印度尼西亚", "phone": "+623137394275", "tax_or_customs_number": "74.205.827.4-611.000"}],
    8: [{"recipient_name": "Lambang Kumara Pramuditha", "address_text": "Jalan Sanggar Kencana Utama No.31, Kelurahan Jatisari, Kecamatan Buah Batu, Kota Bandung 40286, West Java, Indonesia", "city": "Bandung", "region": "West Java", "postal_code": "40286", "country": "印度尼西亚", "tax_or_customs_number": "3273133001920003", "shipping_notes": "DHL 6859107662"}],
    9: [{"recipient_name": "Saiful Karim", "address_text": "Dusun Kramat, Desa Jetis RT02/RW 01 (Depan toko bangunan UD Tiga Putra), Kecamatan Curahdami, Bondowoso 68251, Indonesia", "city": "Bondowoso", "postal_code": "68251", "country": "印度尼西亚", "tax_or_customs_number": "NPWP 86.029.664.9-656.000; NIK 3511110802840003", "shipping_notes": "DHL 1179175406"}],
    10: [{"recipient_name": "Khalid Abdullah", "address_text": "Kontrakan Bang Acha, pintu no 02, Gg. H. Rijin No 174 RT.001/RW.009, Jatimakmur, Kec. Pondok Gede, Kota Bekasi, Jawa Barat 17413", "city": "Bekasi", "region": "Jawa Barat", "postal_code": "17413", "country": "印度尼西亚", "tax_or_customs_number": "210385654447000", "shipping_notes": "DHL 778067619207"}],
    11: [{"recipient_name": "Deo", "address_text": "Jln. Madukoro Blok AE-3, Perum Gading Permai, Sektor 5, Solobaru, Kec. Grogol, Sukoharjo, Jawa Tengah 57552, Indonesia", "city": "Sukoharjo", "region": "Jawa Tengah", "postal_code": "57552", "country": "印度尼西亚", "tax_or_customs_number": "41.802.386.7-532.000", "shipping_notes": "DHL 6859105411"}],
    12: [{"recipient_name": "Rendy Adha", "address_text": "Griya Pindad Asri Blok A1 No15, Jelegong - Rancaekek, Kab. Bandung, Jawa Barat 40394, Indonesia", "city": "Bandung", "region": "Jawa Barat", "postal_code": "40394", "country": "印度尼西亚", "tax_or_customs_number": "81.349.948.0-444.000"}],
    36: [{"recipient_name": "Aleksandar Stojkovic", "address_text": "Sutjeska 1/26a/7, 11210 Krnjaca, Belgrade, Serbia", "city": "Belgrade", "postal_code": "11210", "country": "塞尔维亚"}],
    79: [{"recipient_name": "Manjoo Lee", "address_text": "78-12, Waryong-ro 53-gil, Dalseo-gu, Daegu 42627, Republic of Korea", "city": "Daegu", "postal_code": "42627", "country": "韩国", "tax_or_customs_number": "P170021474991"}],
    80: [{"recipient_name": "Andrey Viktorovich Vorobiev", "address_text": "11-2-52 Glagoleva generala st., Moscow 123103, Russia", "city": "Moscow", "postal_code": "123103", "country": "俄罗斯", "phone": "+79166969173", "shipping_notes": "发票报关总价低于 200 欧；不要出现公司名，只用个人名字；走 EMS", "link_contact": False}],
    112: [
        {"recipient_name": "Nicolas Hattry", "address_text": "100 rue Saint Ghislain, 50000 Saint-Lo, France", "city": "Saint-Lo", "postal_code": "50000", "country": "法国", "email": "nico_cpk@overclocking.com", "phone": "+33620420403", "source_suffix": "nicolas"},
        {"recipient_name": "Alexis Duluard", "address_text": "12 rue des Rouliers, Appartement 24, 53810 Changé, France", "city": "Changé", "postal_code": "53810", "country": "法国", "email": "vertex@overclocking.com", "phone": "06.31.91.81.04", "source_suffix": "alexis", "link_contact": False},
    ],
    113: [{"recipient_name": "Nefedov Petr Victorovich", "address_text": "Russia, Moskovskaya oblast, Mytishchi, Yubilejnaya street, house 4, apartment 228, 141021", "city": "Mytishchi", "region": "Moskovskaya oblast", "postal_code": "141021", "country": "俄罗斯"}],
    115: [{"recipient_name": "Reyan Siddiqui", "address_text": "H/No B-688, Gola Gali Choori Bazar, Fateh Cloth Market, Sukkur, Sindh 74700, Pakistan", "city": "Sukkur", "region": "Sindh", "postal_code": "74700", "country": "巴基斯坦"}],
    116: [{"recipient_name": "Alin Yerlan Kanatovich", "address_text": "21 Neftezavodskaya Street, Omsk 644053, Russia", "city": "Omsk", "postal_code": "644053", "country": "俄罗斯"}],
    117: [{"recipient_name": "Eliseo Traficante", "address_text": "Via dell'Edilizia 10, 85100 Potenza (PZ), Italy", "city": "Potenza", "region": "PZ", "postal_code": "85100", "country": "意大利"}],
    118: [{"recipient_name": "Guilherme Evangelista Rocha", "address_text": "Rua Grécia 286, Conjunto Henrique Sapori, Ribeirão das Neves, MG 33823-090, Brazil", "city": "Ribeirão das Neves", "region": "MG", "postal_code": "33823-090", "country": "巴西", "tax_or_customs_number": "CPF 076.146.096-97"}],
    119: [{"recipient_name": "Juan Botero", "address_text": "Carrera 19g #59-61 Sur, Bogotá 111941, Colombia", "city": "Bogotá", "postal_code": "111941", "country": "哥伦比亚"}],
    121: [{"recipient_name": "Yassine Rahhou", "address_text": "Av Ennakhil, M'hamid 5 Bloc 3, Marrakech 40160, Morocco", "city": "Marrakech", "postal_code": "40160", "country": "摩洛哥"}],
    123: [{"recipient_name": "ZeeSid Ahmed", "address_text": "Waseem Dupada Gali, Kapra Market, Sukkur, Sindh 65200, Pakistan", "city": "Sukkur", "region": "Sindh", "postal_code": "65200", "country": "巴基斯坦", "link_contact": False}],
    132: [{"recipient_name": "Alex Ziskind", "address_text": "2817 Spencer Rd., Chevy Chase, MD 20815, United States", "city": "Chevy Chase", "region": "MD", "postal_code": "20815", "country": "美国"}],
    135: [{"recipient_name": "Mohamed Mamouni", "address_text": "Khemis Kara, Lakhdaria, Bouira 10002, Algeria", "city": "Lakhdaria", "region": "Bouira", "postal_code": "10002", "country": "阿尔及利亚"}],
    136: [{"recipient_name": "Mohammed Lamine Merabt", "address_text": "200 Logements, Sidi Khouiled, Ouargla 30035, Algeria", "city": "Ouargla", "postal_code": "30035", "country": "阿尔及利亚"}],
    137: [{"recipient_name": "Andreas Bunen", "address_text": "eTonix Interactive GmbH, Niedersachsenring 30a, 26789 Leer, Germany", "city": "Leer", "postal_code": "26789", "country": "德国"}],
}

REMAINING_NOTES = {
    5: "Skype: live:.cid.c7c1780be47e150c",
    6: "UP Novy：+62 877-8931-5354；官网：https://arx.co.id/advertise；WeChat 有隐私设置",
    79: "Skype: lmjy2k",
    80: "媒体咨询：reklama3@overclockers.ru",
    112: "第二联系人：Alexis Duluard；vertex@overclocking.com；06.31.91.81.04",
}

CONTACT_REPAIRS = {
    7: {"telegram": "https://t.me/glennjulifer88", "notes": None},
    62: {"name": "Paul Holmes", "role": "Founder & Chair", "email": "pholmes@provokemedia.com", "notes": "其他联系人：Sarah Parsonage (sarah@provokemedia.com)；Patrick Drury (pdrury@provokemedia.com)"},
    72: {"name": "Sarah Vizard", "role": "Editor", "email": "sv@raconteur.net", "notes": "其他编辑部联系人：Francesca Cassidy fc@raconteur.net；Rohan Banerjee rba@raconteur.net；Sam Forsdick sfo@raconteur.net；Clara Murray cmm@raconteur.net；Ian Deering id@raconteur.net；James Sutton js@raconteur.net；Gem Sofianos gs@raconteur.net；Neil Cole nc@raconteur.net；Christina Ryder cr@raconteur.net"},
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    plan = {"contact_ids": sorted(ADDRESSES), "address_count": sum(map(len, ADDRESSES.values())), "contact_repairs": sorted(CONTACT_REPAIRS)}
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        print("Dry-run only; add --apply to write changes.")
        return

    db = SessionLocal()
    summary = defaultdict(int)
    try:
        for contact_id, candidates in ADDRESSES.items():
            contact = db.get(Contact, contact_id)
            if not contact or not (contact.notes or "").strip():
                summary["skipped_missing_source"] += 1
                continue
            source_note = contact.notes.strip()
            has_default = bool(db.query(ShippingAddress.id).filter(ShippingAddress.media_id == contact.media_id, ShippingAddress.is_default.is_(True)).first())
            for index, candidate in enumerate(candidates):
                data = dict(candidate)
                suffix = data.pop("source_suffix", str(index + 1))
                link_contact = data.pop("link_contact", True)
                source_key = f"contact-note:{contact_id}:{suffix}\n{source_note}"
                if db.query(ShippingAddress.id).filter(ShippingAddress.source_text == source_key).first():
                    summary["addresses_already_present"] += 1
                    continue
                db.add(ShippingAddress(
                    media_id=contact.media_id,
                    contact_id=contact.id if link_contact else None,
                    phone=data.pop("phone", None) or contact.phone,
                    email=data.pop("email", None) or contact.email,
                    source_text=source_key,
                    is_default=not has_default,
                    is_confirmed=True,
                    **data,
                ))
                has_default = True
                summary["addresses_created"] += 1
            contact.notes = REMAINING_NOTES.get(contact_id)
            summary["contact_notes_cleaned"] += 1

        for contact_id, values in CONTACT_REPAIRS.items():
            contact = db.get(Contact, contact_id)
            if not contact:
                continue
            for key, value in values.items():
                setattr(contact, key, value)
            summary["contacts_repaired"] += 1

        db.flush()
        for media in db.query(Media).all():
            has_method = any(any((contact.email, contact.phone, contact.whatsapp, contact.telegram, contact.brief_email, contact.press_release_email)) for contact in media.contacts)
            if not has_method:
                media.verification_status = "待核验"
                summary["media_flagged_missing_contact"] += 1

        user = db.query(User).filter(User.role == "Admin").first()
        db.add(AuditLog(
            user_id=user.id if user else None,
            action="clean_contact_addresses",
            entity_type="crm_data",
            entity_id="2026-08-13",
            before_json=json.dumps(plan, ensure_ascii=False),
            after_json=json.dumps(dict(summary), ensure_ascii=False),
            reason="将人工复核的收件地址从联系人备注迁移至地址表，修复错位联系方式，并标记仍缺联系方式的媒体",
        ))
        db.commit()
        print(json.dumps(dict(summary), ensure_ascii=False, indent=2))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
