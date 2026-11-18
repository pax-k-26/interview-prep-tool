from panelpractice.director import END_TOKEN, parse

NAMES = ["Dana Whitfield", "Marcus Hale", "Dr. Priya Raman"]


def test_two_speakers():
    segs = parse("Dana Whitfield: Welcome.\nMarcus Hale: Tell me about your budget.", NAMES)
    assert [(s.speaker, s.text) for s in segs] == [("Dana Whitfield", "Welcome."), ("Marcus Hale", "Tell me about your budget.")]


def test_name_with_title_dot_and_markdown_noise():
    assert parse("**Dr. Priya Raman**: How do you work with physicians?", NAMES)[0].speaker == "Dr. Priya Raman"


def test_unlabelled_text_goes_to_previous_then_first():
    assert parse("Hello there.", NAMES)[0].speaker == "Dana Whitfield"
    segs = parse("Marcus Hale: First part.\nSecond part.", NAMES)
    assert len(segs) == 1 and segs[0].text == "First part. Second part."


def test_end_token_stripped_and_blank_dropped():
    segs = parse(f"Dana Whitfield: Thank you, goodbye. {END_TOKEN}\n\n", NAMES)
    assert segs[0].text == "Thank you, goodbye."


def stream(chunks):
    from panelpractice.director import StreamParser
    p, out = StreamParser(NAMES), []
    for c in chunks:
        out += list(p.feed(c))
    return out + list(p.feed("", final=True))


def test_stream_splits_sentences_as_they_arrive():
    assert stream(["Dana Whitfield: Welcome. ", "Tell me", " about yourself?"]) == [
        ("Dana Whitfield", "Welcome."), ("Dana Whitfield", "Tell me about yourself?")]


def test_stream_speaker_change_without_newline_and_leaked_narration():
    out = stream(["Dana Whitfield: We proceed with Marcus.", "Marcus Hale: Thank you. Why?"])
    assert [w for w, _ in out] == ["Dana Whitfield", "Marcus Hale", "Marcus Hale"]


def test_stream_does_not_split_on_dr_abbreviation():
    out = stream(["Dana Whitfield: Dr. Priya Raman will ask next. ", "Dr. Priya Raman: Hello."])
    assert out == [("Dana Whitfield", "Dr. Priya Raman will ask next."), ("Dr. Priya Raman", "Hello.")]


def test_stream_label_split_across_tokens():
    assert stream(["Dana Whitfield: Hi. Marcus", " Hale: Hello there."])[-1] == ("Marcus Hale", "Hello there.")
