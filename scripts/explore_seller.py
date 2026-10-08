"""Pick one active seller from the dataset and print their recent history.
Run: python scripts/explore_seller.py [glid]
"""
import sys
import pandas as pd

D = "Dataset/Global Context - Seller Dataset/"

profile = pd.read_csv(D + "gc_seller_profile.csv")
print("Total sellers:", len(profile))

if len(sys.argv) > 1:
    glid = int(sys.argv[1])
else:
    top = profile.sort_values("eng_enq_received_90d", ascending=False).head(5)
    print(top[["fk_glusr_usr_id", "company_name", "seller_city", "top_category_1", "eng_enq_received_90d"]].to_string())
    glid = int(top.iloc[0]["fk_glusr_usr_id"])

print("\n=== GLID", glid, "===")
p = profile[profile["fk_glusr_usr_id"] == glid].iloc[0]
for c in ["company_name", "seller_city", "seller_state", "business_type", "top_category_1", "top_category_2",
          "is_paid", "gst_verified_flag", "do_not_call_requested", "showed_frustration", "past_objections",
          "bot_attempts", "bot_answered", "calls_meeting_fixed", "eng_enq_received_90d", "eng_enq_replies_90d"]:
    print(f"{c:28s} {p[c]}")

def show(name, file, key, date_col, cols):
    df = pd.read_csv(D + file, low_memory=False)
    df = df[df[key] == glid].sort_values(date_col, ascending=False)
    print(f"\n--- {name}: {len(df)} rows (latest {df[date_col].iloc[0] if len(df) else '-'}) ---")
    if len(df):
        print(df[cols].head(5).to_string(index=False, max_colwidth=60))

show("Enquiries received", "gc_enquiries_received.csv", "seller_glid", "enquiry_date",
     ["enquiry_date", "product_name", "buyer_city", "read_status", "message"])
show("Enquiry replies", "gc_enquiry_messages.csv", "seller_glid", "reply_date",
     ["reply_date", "message_from", "reply_text"])
show("Buyer calls", "gc_buyer_calls_received.csv", "seller_glid", "call_datetime",
     ["call_datetime", "call_status", "talk_sec"])
show("Buyleads bought", "gc_buyleads_bought.csv", "seller_glid", "purchase_date",
     ["purchase_date", "keyword", "credits_used", "distance_city"])
show("VANI bot calls", "gc_bot_calls.csv", "fk_glusr_usr_id", "call_start_time",
     ["call_start_time", "disposition_label", "meeting_fixed", "lead_call_summary"])
show("WhatsApp chatbot", "gc_whatsapp_chatbot_conversations.csv", "glid", "entry_date",
     ["entry_date", "user_message", "bot_reply", "intent"])
show("Executive calls", "gc_executive_calls.csv", "fk_glusr_usr_id", "call_start_time",
     ["call_start_time", "status", "call_duration", "module"])
show("Buyer call extractions", "gc_buyer_call_extractions.csv", "glid", "call_date",
     ["call_date", "seller_role_on_call", "products_discussed", "prices_quoted"])
