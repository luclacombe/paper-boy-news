"""Tests for post-extraction content filters."""

from __future__ import annotations

import pytest

from paper_boy.filters import (
    check_quality,
    detect_paywall,
    strip_bbc_related,
    strip_figcaption_paragraph_dupe,
    strip_junk,
    strip_lede_dupe,
    strip_sciencedaily_metadata,
    strip_section_junk,
    strip_trailing_junk,
)


# --- strip_junk (parametrized) ---


class TestStripJunk:
    @pytest.mark.parametrize("junk_text", [
        "Advertisement",
        "ADVERTISEMENT",
        "Follow us on Twitter",
        "Follow us on Facebook",
        "Follow us on Twitter @BBCAfrica, on Facebook at BBC Africa or on Instagram at bbcafrica",
        "Go to BBCAfrica.com for more news from the African continent.",
        "Go to bbc.com for more",
        "Sign up for our daily newsletter",
        "Sign up to Morning Edition",
        "Subscribe to our newsletter",
        "Related articles",
        "Related article",
        "You may also be interested in",
        "More from Technology",
        "Read more:",
        "Share this article",
        "Share on Twitter",
        "Power up with unlimited access to WIRED. Get best-in-class reporting. Subscribe Today.",
        "Breaking space news, the latest updates on rocket launches!",
        "You are now subscribed",
        "Your newsletter sign-up was successful",
        "Want to add more newsletters?",
        "Enjoying our latest content and features",
        "Access the most recent journalism from our team",
        "Explore the latest features and updates",
        "Thank you for visiting nature.com and reading our articles",
        "Story Source:",
        "Cite This Page:",
        "CLICK HERE TO DOWNLOAD THE FOX NEWS APP",
        "CLICK HERE FOR MORE SPORTS COVERAGE ON FOXNEWS.COM",
        "CLICK HERE TO SIGN UP FOR OUR LIFESTYLE NEWSLETTER",
        "CLICK HERE TO GET THE FOX NEWS APP",
        "LIKE WHAT YOU'RE READING? CLICK HERE FOR MORE ENTERTAINMENT NEWS",
        "Follow Fox News Digital's sports coverage on X and subscribe to the Fox News Sports Huddle newsletter.",
        # Source-specific preambles
        "Agenda-setting intelligence, analysis and advice for the global fashion community.",
        "These highlights were written by the reporters and editors of ProPublica.",
        "We've lifted the paywall. Foreign Policy's best stories, accessible for all.",
        "Roula Khalaf, Editor of the FT, selects her favourite stories in this weekly newsletter.",
        "Roula Khalaf selects her favourite stories to read in this newsletter.",
        "Get your daily dose of health and medicine every weekday with STAT's free newsletter Morning Rounds. Sign up here.",
        "Good morning and welcome to The Downshift, your daily briefing.",
        # Navigation CTAs
        "Go Deeper: Fashion Sustainability Report 2026",
        "Learn more: How AI Is Reshaping Fashion Design",
        # Guardian sign-up variant
        "Sign up: AU Breaking News email",
        # NPR newsletter
        "You're reading the Up First newsletter. Subscribe here to get it delivered to your inbox.",
        "Good morning. You're reading the Up First newsletter. Subscribe here to get it delivered to your inbox, and listen to the Up First podcast for all the news you need to start your day.",
        "This newsletter was edited by Suzanne Nuyen.",
        # Post metadata
        "This post originally published at March 9 at 6:56 p.m. PT",
        "Materials provided by MIT. Note: Content may be edited for style and length.",
        # BBC solicitation
        "If you have information about this story that you would like to share, please email us.",
        # AP separator
        "___",
        # Wired
        "In Your Inbox: For dispatches from the intersection of tech and culture.",
        "What Say You? Let us know what you think about this article in the comments below.",
        # Kiplinger
        "Profit and prosper with the best of expert advice on investing and taxes.",
        # Donation/partnership
        "This coverage is made possible through a partnership between Grist and The Texas Tribune.",
        "If you've ever considered going solar, there's no better time than right now.",
        # Free newsletter label
        "Free newsletter",
        # Space.com ad break / comment system (Batch 9)
        "Article continues below",
        "You must confirm your public display name before commenting",
        "Please logout and then login again, you will then be prompted to enter your display name.",
        # FT myFT Digest (Batch 9)
        "Simply sign up to the US Morning Briefing myFT Digest -- delivered directly to your inbox.",
        # Bloomberg podcast (Batch 9)
        "Subscribe to the Bloomberg Daybreak Podcast on Apple, Spotify and other Podcast Platforms",
        # Politico Playbook (Batch 9)
        "Like this content? Consider signing up for POLITICO's Playbook newsletter.",
        # Kiplinger subscription CTA (Batch 8)
        "Become a smarter, better informed investor. Subscribe from just $24.99, plus get up to 4 Special Issues",
        # Kiplinger mid-article newsletter CTA (Batch 8) — matches any "Sign up for [X], our free [Y] newsletter"
        "Looking for more timely stock market news to help gauge the health of your portfolio? Sign up for Closing Bell, our free newsletter that's delivered straight to your inbox at the close of each trading day.",
        "Looking for expert tips to grow and preserve your wealth? Sign up for Adviser Intel, our free, twice-weekly newsletter.",
        # Kiplinger Adviser Intel heading/boilerplate (Batch 8)
        "About Adviser Intel",
        "The author of this article is a participant in Kiplinger\u2019s Adviser Intel program, a curated network of trusted financial professionals who share expert insights on wealth building and preservation.",
        # Kiplinger newsletter/magazine CTAs (Batch 8)
        "Get practical help to make better financial decisions in your everyday life, from spending to savings on top deals. Subscribe to Kiplinger\u2019s free newsletter, A Step Ahead.",
        "Note: This item first appeared in Kiplinger Personal Finance Magazine, a monthly, trustworthy source of advice and guidance. Subscribe to help you make more money and keep more of the money you make here.",
        "Pack your bags and earn rewards. Kiplinger chose the best travel rewards cards for airline, hotel and other perks to help you save money.",
        "Interested in more information for financial professionals? Sign up for Kiplinger\u2019s twice-monthly free newsletter, Adviser Intel.",
        "From just $107.88 $24.99 for Kiplinger Personal Finance",
    ])
    def test_removes_junk_paragraph(self, junk_text):
        html = f"<p>Good content here.</p><p>{junk_text}</p>"
        result = strip_junk(html)
        assert junk_text not in result
        assert "Good content" in result

    @pytest.mark.parametrize("safe_text", [
        "The company decided to share this article with investors before the earnings call.",
        "The advertisement industry is worth billions.",
        "Click here to see the full report on the government website.",
        "The company provided materials for the research project.",
        "She decided to sign up for the marathon next month.",
        "The editor originally published the story in 2020.",
        # Batch 9 — contextual uses that must NOT be stripped
        "The article continues below the fold with more analysis.",
        "Users must confirm their identity before accessing the system.",
        "She decided to subscribe to the Bloomberg Terminal for market data.",
    ])
    def test_preserves_contextual_mentions(self, safe_text):
        html = f"<p>{safe_text}</p>"
        result = strip_junk(html)
        assert safe_text[:30] in result

    def test_removes_div_junk(self):
        html = "<p>Story.</p><div>Advertisement</div>"
        result = strip_junk(html)
        assert "Advertisement" not in result

    def test_junk_with_inner_tags(self):
        html = '<p><strong>Follow us on</strong> <a href="#">Twitter</a></p>'
        result = strip_junk(html)
        assert "Follow us on" not in result

    def test_preserves_good_content_around_junk(self):
        html = "<p>Good content here.</p><p>Advertisement</p><p>More content.</p>"
        result = strip_junk(html)
        assert "Good content" in result
        assert "More content" in result


# --- strip_sciencedaily_metadata ---


class TestStripScienceDailyMetadata:
    def test_removes_metadata_list(self):
        html = (
            '<ul><li>Date:</li><li>March 9, 2026</li>'
            '<li>Source:</li><li>MIT</li>'
            '<li>Summary:</li><li>Scientists found...</li>'
            '<li>Share:</li><li/></ul>'
            '<p>The actual article content.</p>'
        )
        result = strip_sciencedaily_metadata(html)
        assert "Date:" not in result
        assert "Source:" not in result
        assert "actual article content" in result

    def test_preserves_normal_lists(self):
        html = "<ul><li>Point one</li><li>Point two</li></ul>"
        result = strip_sciencedaily_metadata(html)
        assert result == html

    def test_preserves_list_with_date_only(self):
        """Should not match if Source: is missing."""
        html = "<ul><li>Date:</li><li>March 9</li></ul>"
        result = strip_sciencedaily_metadata(html)
        assert result == html

    def test_removes_story_source_trailing(self):
        """Story Source / Journal Reference / Cite This Page trailing blocks."""
        html = (
            "<p>Article content here.</p>"
            "<p>Story Source:</p>"
            "<p>Materials provided by MIT.</p>"
            "<p>Journal Reference:</p>"
            "<ul><li>Smith et al. Nature, 2026</li></ul>"
            "<p>Cite This Page:</p>"
        )
        result = strip_sciencedaily_metadata(html)
        assert "Article content" in result
        assert "Story Source:" not in result
        assert "Journal Reference:" not in result
        assert "Cite This Page:" not in result

    def test_preserves_content_before_story_source(self):
        html = "<p>First paragraph.</p><p>Second paragraph.</p><p>Story Source:</p><p>MIT</p>"
        result = strip_sciencedaily_metadata(html)
        assert "First paragraph" in result
        assert "Second paragraph" in result
        assert "Story Source:" not in result

    def test_removes_journal_references_plural(self):
        """Plural 'Journal References:' variant."""
        html = (
            "<p>Article content here.</p>"
            "<p>Journal References:</p>"
            "<ul><li>Smith et al. 2026</li><li>Jones et al. 2025</li></ul>"
        )
        result = strip_sciencedaily_metadata(html)
        assert "Article content" in result
        assert "Journal References:" not in result


# --- strip_bbc_related ---


class TestStripBbcRelated:
    def test_removes_related_topics_section(self):
        html = (
            "<p>Article content.</p>"
            "<h2>Related topics</h2>"
            "<ul><li>Published17 October 2025</li>"
            '<li><figure><img src="img.jpg" alt="test"/></figure></li></ul>'
        )
        result = strip_bbc_related(html)
        assert "Article content" in result
        assert "Related topics" not in result
        assert "Published17" not in result

    def test_preserves_content_without_related(self):
        html = "<p>Normal content.</p><h2>Analysis</h2><p>More content.</p>"
        result = strip_bbc_related(html)
        assert result == html

    def test_case_insensitive(self):
        html = "<p>Content.</p><h2>RELATED TOPICS</h2><ul><li>stuff</li></ul>"
        result = strip_bbc_related(html)
        assert "RELATED TOPICS" not in result


# --- strip_section_junk (stub — no-op with empty rules) ---


class TestStripSectionJunk:
    def test_removes_read_this_next_section(self):
        html = (
            "<p>Article content.</p>"
            "<h2>Read this next</h2>"
            "<ul><li>Related article 1</li><li>Related article 2</li></ul>"
        )
        result = strip_section_junk(html)
        assert "Article content" in result
        assert "Read this next" not in result
        assert "Related article" not in result

    def test_removes_recommended_stories(self):
        html = (
            "<p>Article content.</p>"
            "<h2>Recommended Stories</h2>"
            "<ul><li>Story 1</li></ul>"
            "<p>More junk.</p>"
        )
        result = strip_section_junk(html)
        assert "Article content" in result
        assert "Recommended Stories" not in result

    def test_recommended_stories_preserves_content_after_next_heading(self):
        """Al Jazeera fix: to_next_heading scope keeps content past next heading."""
        html = (
            "<p>Main article body.</p>"
            "<h3>Recommended Stories</h3>"
            "<ul><li>Rec 1</li></ul>"
            "<h2>Analysis</h2>"
            "<p>Important analysis content.</p>"
        )
        result = strip_section_junk(html)
        assert "Main article body" in result
        assert "Recommended Stories" not in result
        assert "Rec 1" not in result
        assert "Analysis" in result
        assert "Important analysis content" in result

    def test_removes_contact_us_to_next_heading(self):
        html = (
            "<p>Content.</p>"
            "<h4>Contact Us</h4>"
            "<p>You can reach us at tips@example.com or on Signal.</p>"
            "<h2>Related Stories</h2>"
            "<p>More content here.</p>"
        )
        result = strip_section_junk(html)
        assert "Content." in result
        assert "Contact Us" not in result
        assert "Signal" not in result
        assert "Related Stories" in result
        assert "More content here" in result

    def test_removes_got_a_tip_section(self):
        html = (
            "<p>Article text.</p>"
            "<h4>Got a Tip?</h4>"
            "<p>Send tips to tips@wired.com</p>"
            "<h3>Next Section</h3>"
            "<p>More article.</p>"
        )
        result = strip_section_junk(html)
        assert "Article text" in result
        assert "Got a Tip" not in result
        assert "Next Section" in result

    def test_removes_newsletter_signup_block(self):
        """New Scientist pattern: h4 Sign up to [Name] + up to 3 siblings."""
        html = (
            "<p>Science content.</p>"
            "<h4>Sign up to Our Human Story</h4>"
            "<p>Get the latest discoveries about human evolution.</p>"
            "<figure><figcaption>New Scientist</figcaption></figure>"
            "<p>More science content that should be kept.</p>"
            "<p>Even more content that should also survive.</p>"
        )
        result = strip_section_junk(html)
        assert "Science content" in result
        assert "Sign up to" not in result
        assert "human evolution" not in result  # within 3 siblings
        # 4th sibling should survive the bounded strip
        assert "Even more content" in result

    def test_newsletter_signup_stops_at_heading(self):
        """next_3 scope still stops at headings even before limit."""
        html = (
            "<p>Content.</p>"
            "<h4>Sign up to Weekly</h4>"
            "<p>Description.</p>"
            "<h3>Next Section</h3>"
            "<p>Preserved.</p>"
        )
        result = strip_section_junk(html)
        assert "Sign up to" not in result
        assert "Description" not in result
        assert "Next Section" in result
        assert "Preserved" in result

    def test_preserves_content_with_no_matching_headings(self):
        html = "<p>Content.</p><h2>Analysis</h2><p>More content.</p>"
        result = strip_section_junk(html)
        assert "Analysis" in result
        assert "More content" in result

    def test_removes_what_were_reading(self):
        html = (
            "<p>Newsletter content.</p>"
            "<h2>What we're reading</h2>"
            "<ul><li>Link 1</li><li>Link 2</li></ul>"
        )
        result = strip_section_junk(html)
        assert "Newsletter content" in result
        assert "What we" not in result
        assert "Link 1" not in result

    def test_removes_behind_the_scenes(self):
        """Rolling Stone production credits stripped from heading onward."""
        html = (
            "<p>The interview concluded with a discussion about her next album.</p>"
            "<h2>Behind the Scenes</h2>"
            "<h5>Photographs by Dario Calmese</h5>"
            "<p>Styling by Solange Franklin. Hair by Jawara. Makeup by Priscilla Ono.</p>"
        )
        result = strip_section_junk(html)
        assert "interview concluded" in result
        assert "Behind the Scenes" not in result
        assert "Styling by" not in result

    def test_removes_top_comment_by(self):
        """Electrek reader comments stripped, next heading preserved."""
        html = (
            "<p>Tesla reported strong quarterly deliveries.</p>"
            "<h2>Top comment by EV_Wisconsin</h2>"
            "<p>Great to see the numbers improving quarter over quarter.</p>"
            "<h2>Related Articles</h2>"
            "<p>More EV news.</p>"
        )
        result = strip_section_junk(html)
        assert "Tesla reported" in result
        assert "Top comment by" not in result
        assert "EV_Wisconsin" not in result
        assert "Related Articles" in result
        assert "More EV news" in result

    def test_removes_kiplinger_signup_heading(self):
        """Kiplinger 'Sign up for Kiplinger's Free Newsletters' heading."""
        html = (
            "<p>Investment advice.</p>"
            "<h2>Sign up for Kiplinger's Free Newsletters</h2>"
            "<p>Profit and prosper with expert advice.</p>"
            "<h2>Market Analysis</h2>"
            "<p>Stocks fell today.</p>"
        )
        result = strip_section_junk(html)
        assert "Investment advice" in result
        assert "Sign up for Kiplinger" not in result
        assert "Market Analysis" in result
        assert "Stocks fell today" in result

    def test_removes_related_content_to_end(self):
        """Kiplinger 'Related content' trailing section stripped entirely."""
        html = (
            "<p>Article conclusion.</p>"
            "<h3>Related content</h3>"
            "<ul><li>Article 1</li><li>Article 2</li></ul>"
            "<figure><figcaption>Author Name</figcaption></figure>"
            "<p>Author bio paragraph.</p>"
        )
        result = strip_section_junk(html)
        assert "Article conclusion" in result
        assert "Related content" not in result
        assert "Author bio" not in result


# --- strip_trailing_junk (stub — no-op with empty rules) ---


class TestStripTrailingJunk:
    def test_preserves_reuters_byline_credit(self):
        """Reuters wire bylines are legitimate journalist credits — must be kept."""
        html = (
            "<p>Article content here.</p>"
            "<p>Final paragraph of story.</p>"
            "<small>Reporting by John Smith; editing by Jane Doe</small>"
        )
        result = strip_trailing_junk(html)
        assert "Reporting by" in result

    def test_removes_got_a_tip_trailing(self):
        html = (
            "<p>Article text.</p>"
            "<p>Got a tip? tips@thedrive.com</p>"
        )
        result = strip_trailing_junk(html)
        assert "Article text" in result
        assert "Got a tip" not in result

    def test_preserves_content_with_no_trailing_junk(self):
        html = "<p>First.</p><p>Second.</p><p>Third.</p>"
        result = strip_trailing_junk(html)
        assert "First" in result
        assert "Second" in result
        assert "Third" in result

    def test_removes_ap_section_link(self):
        html = (
            "<p>Story conclusion.</p>"
            "<p>AP Sports: https://apnews.com/sports</p>"
        )
        result = strip_trailing_junk(html)
        assert "Story conclusion" in result
        assert "AP Sports" not in result

    def test_handles_html_comments_without_crashing(self):
        """AV Club fix: HTML comments in children must not crash text_content()."""
        html = (
            "<p>Article body text.</p>"
            "<!-- CMS editorial comment -->"
            "<p>Got a tip? tips@example.com</p>"
        )
        result = strip_trailing_junk(html)
        assert "Article body text" in result
        assert "Got a tip" not in result

    def test_preserves_content_around_html_comments(self):
        """HTML comments between content paragraphs are harmless."""
        html = (
            "<p>First paragraph.</p>"
            "<!-- analytics tag -->"
            "<p>Second paragraph.</p>"
        )
        result = strip_trailing_junk(html)
        assert "First paragraph" in result
        assert "Second paragraph" in result


# --- strip_lede_dupe ---


class TestStripLedeDupe:
    def test_removes_reuters_style_lede_duplicate(self):
        """Reuters pattern: <em>Summary</em> <small>By Author</small> <p>Summary</p>."""
        html = (
            "<em>Oil prices rose on Monday as tensions in the Middle East escalated.</em>"
            "<small>By John Smith</small>"
            "<p>Oil prices rose on Monday as tensions in the Middle East escalated.</p>"
            "<p>Brent crude futures gained 1.2% to $82.50 a barrel.</p>"
        )
        result = strip_lede_dupe(html)
        assert "Oil prices rose" in result  # <em> kept
        assert result.count("Oil prices rose") == 1  # duplicate <p> removed
        assert "Brent crude" in result  # rest of article preserved

    def test_removes_reuters_wrapped_em_in_p(self):
        """Reuters actual pattern: <p><em>Summary</em></p> <p><small>By</small></p> <p>Summary</p>."""
        html = (
            "<p><em>Oil prices rose on Monday as tensions in the Middle East escalated.</em></p>"
            "<p><small>By John Smith</small></p>"
            "<p>Oil prices rose on Monday as tensions in the Middle East escalated.</p>"
            "<p>Brent crude futures gained 1.2% to $82.50 a barrel.</p>"
        )
        result = strip_lede_dupe(html)
        assert "Oil prices rose" in result
        assert result.count("Oil prices rose") == 1
        assert "Brent crude" in result

    def test_removes_reuters_with_long_byline(self):
        """Reuters with multi-author byline in <p><small> still deduplicates."""
        html = (
            "<p><em>Iran will fight on and keep the Strait of Hormuz shut as leverage.</em></p>"
            "<p><small>By Parisa Hafezi, Maya Gebeily</small></p>"
            "<p>Iran will fight on and keep the Strait of Hormuz shut as leverage.</p>"
            "<p>More article content here.</p>"
        )
        result = strip_lede_dupe(html)
        assert "Iran will fight" in result
        assert result.count("Iran will fight") == 1
        assert "More article content" in result

    def test_preserves_non_matching_opening(self):
        """Don't strip if <em> and <p> text differ."""
        html = (
            "<em>Summary of the story.</em>"
            "<p>The actual article begins here with different text.</p>"
            "<p>Second paragraph.</p>"
        )
        result = strip_lede_dupe(html)
        assert "actual article" in result
        assert "Second paragraph" in result

    def test_preserves_article_without_leading_em(self):
        """Normal articles without opening <em> are untouched."""
        html = (
            "<p>First paragraph of a normal article.</p>"
            "<p>Second paragraph.</p>"
        )
        result = strip_lede_dupe(html)
        assert "First paragraph" in result
        assert "Second paragraph" in result

    def test_ignores_short_em(self):
        """Short <em> text (< 20 chars) is ignored — likely inline emphasis."""
        html = (
            "<em>Breaking:</em>"
            "<p>Breaking: Oil prices rose sharply today.</p>"
        )
        result = strip_lede_dupe(html)
        assert result.count("Breaking") == 2  # both kept — em too short


# --- strip_figcaption_paragraph_dupe ---


class TestStripFigcaptionParagraphDupe:
    def test_removes_npr_style_caption_paragraph(self):
        """NPR pattern: <figure>...<figcaption>Caption</figcaption></figure><p>Caption. Credit</p>."""
        html = (
            "<figure><img src='photo.jpg'/>"
            "<figcaption>Mourners carry the casket at the funeral service.</figcaption>"
            "</figure>"
            "<p>Mourners carry the casket at the funeral service. Anna Moneymaker/Getty Images</p>"
            "<p>The ceremony was held on Tuesday morning.</p>"
        )
        result = strip_figcaption_paragraph_dupe(html)
        assert "Mourners carry" in result  # figcaption kept
        assert result.count("Mourners carry") == 1  # duplicate <p> removed
        assert "ceremony was held" in result  # next paragraph preserved

    def test_preserves_non_matching_paragraph(self):
        """Don't strip <p> that doesn't start with figcaption text."""
        html = (
            "<figure><img src='photo.jpg'/>"
            "<figcaption>A scenic view of the mountains.</figcaption>"
            "</figure>"
            "<p>The hikers set out early in the morning for the summit.</p>"
        )
        result = strip_figcaption_paragraph_dupe(html)
        assert "scenic view" in result
        assert "hikers set out" in result

    def test_preserves_short_figcaption(self):
        """Short figcaptions (< 10 chars) are ignored — could be a credit."""
        html = (
            "<figure><img src='photo.jpg'/>"
            "<figcaption>Reuters</figcaption>"
            "</figure>"
            "<p>Reuters reported that the deal was finalized on Monday.</p>"
        )
        result = strip_figcaption_paragraph_dupe(html)
        assert result.count("Reuters") == 2  # both kept — caption too short

    def test_handles_multiple_figures(self):
        """Dedup works across multiple figures in the same article."""
        html = (
            "<figure><figcaption>First image caption text here.</figcaption></figure>"
            "<p>First image caption text here. Photo by John Smith</p>"
            "<p>Article content between images.</p>"
            "<figure><figcaption>Second image shows the building exterior.</figcaption></figure>"
            "<p>Second image shows the building exterior. Jane Doe/AP</p>"
            "<p>The building was completed in 2024.</p>"
        )
        result = strip_figcaption_paragraph_dupe(html)
        assert result.count("First image caption") == 1
        assert result.count("Second image shows") == 1
        assert "Article content between" in result
        assert "building was completed" in result


# --- detect_paywall ---


class TestDetectPaywall:
    def test_nature_style_paywall(self):
        html = "<p>First paragraph.</p><p>Subscribe to read the full article.</p>"
        assert detect_paywall(html) is True

    def test_log_in_to_continue(self):
        html = "<p>Preview text.</p><p>Log in to continue reading.</p>"
        assert detect_paywall(html) is True

    def test_subscribers_only(self):
        html = "<p>This article is for subscribers only.</p>"
        assert detect_paywall(html) is True

    def test_register_for_free(self):
        html = "<p>Some text.</p><p>Register for free to continue.</p>"
        assert detect_paywall(html) is True

    def test_create_free_account(self):
        html = "<p>Some text.</p><p>Create a free account to continue reading.</p>"
        assert detect_paywall(html) is True

    def test_ft_subscribe_to_unlock(self):
        """FT paywall uses 'subscribe to unlock' phrasing."""
        html = (
            "<p>Subscribe to unlock this article</p>"
            "<p>Try unlimited access Only €1 for 4 weeks</p>"
        )
        assert detect_paywall(html) is True

    def test_project_syndicate_truncation(self):
        """Short URL at end indicates truncated article."""
        html = "<p>Article beginning...</p><p>https://prosyn.org/abc123</p>"
        assert detect_paywall(html) is True

    def test_bitly_truncation(self):
        html = "<p>Article beginning...</p><a>https://bit.ly/xyz</a>"
        assert detect_paywall(html) is True

    def test_false_positive_paywall_strategy_article(self):
        """Article ABOUT paywalls should not be flagged."""
        html = (
            "<p>The New York Times has seen great success with its paywall strategy. "
            "Many publishers are now looking at how to subscribe readers to premium content. "
            "The question is whether readers will pay for news.</p>"
        )
        assert detect_paywall(html) is False

    def test_nature_subscription_preview(self):
        html = "<p>Abstract text.</p><p>This is a preview of subscription content, access via your institution.</p>"
        assert detect_paywall(html) is True

    def test_stat_plus_exclusive(self):
        html = "<p>Teaser.</p><p>This article is exclusive to STAT+ subscribers.</p>"
        assert detect_paywall(html) is True

    def test_clean_article(self):
        html = "<p>This is a normal article about technology and science.</p>"
        assert detect_paywall(html) is False


# --- check_quality ---


class TestCheckQuality:
    def test_too_short_article(self):
        html = "<p>" + " ".join(["word"] * 50) + "</p>"
        assert check_quality(html) is True  # rejected

    def test_borderline_short(self):
        html = "<p>" + " ".join(["word"] * 199) + "</p>"
        assert check_quality(html) is True  # rejected

    def test_sufficient_length(self):
        html = "<p>" + " ".join(["word"] * 250) + "</p>"
        assert check_quality(html) is False  # accepted

    def test_exactly_200_words(self):
        html = "<p>" + " ".join(["word"] * 200) + "</p>"
        assert check_quality(html) is False  # accepted

    def test_correction_notice_short(self):
        html = "<p>Correction: The previous version of this article misstated the date.</p>"
        assert check_quality(html) is True  # rejected

    def test_author_correction_short(self):
        html = "<p>Author Correction: A figure was mislabeled in the original publication.</p>"
        assert check_quality(html) is True  # rejected

    def test_correction_with_full_article(self):
        """Long correction + article body should pass."""
        html = "<p>Correction: The date was wrong.</p><p>" + " ".join(["word"] * 250) + "</p>"
        assert check_quality(html) is False  # accepted


# --- Integration: filter ordering ---


class TestFilterOrdering:
    def test_junk_stripped_before_quality_check(self):
        """Junk paragraphs shouldn't count toward word count."""
        # 180 real words + junk paragraph
        real_words = " ".join(["word"] * 180)
        html = f"<p>{real_words}</p><p>Advertisement</p><p>Follow us on Twitter</p>"
        cleaned = strip_junk(html)
        # After stripping, only 180 words remain — should fail quality
        assert check_quality(cleaned) is True

    def test_junk_stripped_paywall_checked(self):
        """Paywall detection works on cleaned content."""
        html = (
            "<p>Some intro text.</p>"
            "<p>Advertisement</p>"
            "<p>Subscribe to read the full article.</p>"
        )
        cleaned = strip_junk(html)
        assert detect_paywall(cleaned) is True
