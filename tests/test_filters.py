"""Tests for post-extraction content filters."""

from __future__ import annotations

import pytest

from paper_boy.filters import (
    check_quality,
    detect_paywall,
    strip_bbc_related,
    strip_junk,
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
        """New Scientist pattern: h4 Sign up to [Name] + description."""
        html = (
            "<p>Science content.</p>"
            "<h4>Sign up to Our Human Story</h4>"
            "<p>Get the latest discoveries about human evolution.</p>"
            "<figure><figcaption>New Scientist</figcaption></figure>"
            "<h3>Next heading</h3>"
            "<p>More science.</p>"
        )
        result = strip_section_junk(html)
        assert "Science content" in result
        assert "Sign up to" not in result
        assert "Next heading" in result

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
