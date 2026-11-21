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
    test_direct_commands_skip_cards()
    test_countdown_can_be_cancelled()
    print("ok agent")
