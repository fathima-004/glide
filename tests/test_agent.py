"""Glide Agent pieces that don't touch the network or the screen."""
import time

from glide import agent, writer


def test_quick_whatsapp_syntax():
    agent.contacts = lambda: {"didi": "Didi Ltst"}
    assert agent.quick_whatsapp("w-didi varam") == {
        "action": "whatsapp", "contact": "Didi Ltst", "message": "varam", "say": "WhatsApp Didi Ltst: varam"}
    p = agent.quick_whatsapp("W - rahul on the way")
    assert p["contact"] == "Rahul" and p["message"] == "on the way"
    assert agent.quick_whatsapp("w:amma ok")["contact"] == "Amma"
    assert agent.quick_whatsapp("didi varam") is None
    assert agent.quick_whatsapp("wow nice") is None


def test_mail_recipient_comes_from_what_was_written():
    agent.handwriting.ask_json = lambda prompt: {"subject": "Work done", "body": "The work is done.\n\nThanks,"}
    p = agent.quick_mail("mail rashrahn work done")
    assert p["to"] == "rashrahn@gmail.com" and p["subject"] == "Work done"
    assert agent.quick_mail("email Someone@college.edu report sent")["to"] == "Someone@college.edu"
    assert agent.quick_mail("m-rashrahn ok")["to"] == "rashrahn@gmail.com"
    agent.handwriting.ask_json = lambda prompt: {"subject": "Work finished", "body": "The work is finished.",
                                                 "language": "ml"}
    agent.sarvam.translate = lambda text, s, d: "[ml]" + text
    p = agent.quick_mail("mail rashrahn pani kazhinju")          # Manglish -> English email
    assert p["to"] == "rashrahn@gmail.com" and p["subject"] == "Work finished"
    assert p["body"].startswith("Hi,") and "The work is finished." in p["body"]
    p = agent.quick_mail("mail rashrahn ജോലി കഴിഞ്ഞു")  # script -> Malayalam
    assert p["subject"] == "[ml]Work finished"
    assert p["body"].startswith("നമസ്കാരം") and "[ml]The work" in p["body"]
    agent.handwriting.ask_json = lambda prompt: None  # AI down: still sends something sensible
    p = agent.quick_mail("mail rashrahn work done")
    assert p["to"] == "rashrahn@gmail.com" and p["subject"] == "Work done"
    assert agent.quick_mail("w-didi varam") is None


def test_direct_commands_skip_cards():
    assert writer.is_direct_command("w-didi varam")
    assert writer.is_direct_command("mail rashid work completed")
    assert writer.is_direct_command("Email sir leave")
    assert not writer.is_direct_command("sari")
    assert not writer.is_direct_command("didi varam")


def test_countdown_can_be_cancelled():
    agent.COUNTDOWN = 1
    shown = []
    t = time.time()
    assert agent._countdown("Sending", shown.append, lambda: time.time() - t > 0.2) is False
    assert agent._countdown("Sending", shown.append, lambda: False) is True
    assert shown[0].startswith("⚡ Sending in 1")


if __name__ == "__main__":
    test_quick_whatsapp_syntax()
    test_mail_recipient_comes_from_what_was_written()
    test_direct_commands_skip_cards()
    test_countdown_can_be_cancelled()
    print("ok agent")
