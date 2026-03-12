"""Tests for post-extraction content filters."""

from __future__ import annotations

from paper_boy.filters import (
    check_quality,
    detect_paywall,
    strip_bbc_related,
    strip_junk,
    strip_sciencedaily_metadata,
)


# --- strip_junk ---


class TestStripJunk:
    def test_removes_advertisement_paragraph(self):
        html = "<p>Good content here.</p><p>Advertisement</p><p>More content.</p>"
        result = strip_junk(html)
        assert "Advertisement" not in result
        assert "Good content" in result
        assert "More content" in result

    def test_removes_follow_us_footer(self):
        html = "<p>Article text.</p><p>Follow us on Twitter</p>"
        result = strip_junk(html)
        assert "Follow us on" not in result
        assert "Article text" in result

    def test_removes_follow_us_facebook(self):
        html = "<p>Content.</p><p>Follow us on Facebook</p>"
        result = strip_junk(html)
        assert "Follow us on Facebook" not in result

    def test_removes_newsletter_cta(self):
        html = "<p>Story.</p><p>Sign up for our daily newsletter</p>"
        result = strip_junk(html)
        assert "Sign up for" not in result

    def test_removes_subscribe_to_newsletter(self):
        html = "<p>Story.</p><p>Subscribe to our newsletter</p>"
        result = strip_junk(html)
        assert "Subscribe to our newsletter" not in result

    def test_removes_sign_up_to_edition(self):
        html = "<p>Story.</p><p>Sign up to Morning Edition</p>"
        result = strip_junk(html)
        assert "Sign up to" not in result

    def test_removes_related_articles(self):
        html = "<p>Story.</p><p>Related articles</p>"
        result = strip_junk(html)
        assert "Related articles" not in result

    def test_removes_you_may_also(self):
        html = "<p>Story.</p><p>You may also be interested in</p>"
        result = strip_junk(html)
        assert "You may also" not in result

    def test_removes_more_from(self):
        html = "<p>Story.</p><p>More from Technology</p>"
        result = strip_junk(html)
        assert "More from" not in result

    def test_removes_read_more_colon(self):
        html = "<p>Story.</p><p>Read more:</p>"
        result = strip_junk(html)
        assert "Read more:" not in result

    def test_removes_share_this_article(self):
        html = "<p>Story.</p><p>Share this article</p>"
        result = strip_junk(html)
        assert "Share this article" not in result

    def test_removes_share_on(self):
        html = "<p>Story.</p><p>Share on Twitter</p>"
        result = strip_junk(html)
        assert "Share on" not in result

    def test_removes_div_junk(self):
        html = "<p>Story.</p><div>Advertisement</div>"
        result = strip_junk(html)
        assert "Advertisement" not in result

    def test_preserves_contextual_mentions(self):
        """Don't strip paragraphs that mention junk phrases in longer context."""
        html = "<p>The company decided to share this article with investors before the earnings call.</p>"
        result = strip_junk(html)
        assert "The company decided" in result

    def test_preserves_contextual_advertisement(self):
        html = "<p>The advertisement industry is worth billions.</p>"
        result = strip_junk(html)
        assert "advertisement industry" in result

    def test_case_insensitive(self):
        html = "<p>ADVERTISEMENT</p>"
        result = strip_junk(html)
        assert "ADVERTISEMENT" not in result

    def test_junk_with_inner_tags(self):
        html = '<p><strong>Follow us on</strong> <a href="#">Twitter</a></p>'
        result = strip_junk(html)
        assert "Follow us on" not in result

    def test_removes_follow_us_with_trailing_text(self):
        """BBC-style: 'Follow us on Twitter @BBCAfrica, on Facebook...'"""
        html = "<p>Story.</p><p>Follow us on Twitter @BBCAfrica, on Facebook at BBC Africa or on Instagram at bbcafrica</p>"
        result = strip_junk(html)
        assert "Follow us on" not in result

    def test_removes_bbc_go_to_footer(self):
        html = "<p>Story.</p><p>Go to BBCAfrica.com for more news from the African continent.</p>"
        result = strip_junk(html)
        assert "Go to BBC" not in result

    def test_removes_bbc_go_to_short(self):
        html = "<p>Story.</p><p>Go to bbc.com for more</p>"
        result = strip_junk(html)
        assert "Go to bbc.com" not in result


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


# --- strip_junk: new patterns ---


class TestStripJunkNewPatterns:
    def test_removes_wired_subscribe_cta(self):
        html = (
            "<p>Article text.</p>"
            "<p>Power up with unlimited access to WIRED. Get best-in-class "
            "reporting. Subscribe Today.</p>"
        )
        result = strip_junk(html)
        assert "Power up" not in result
        assert "Article text" in result

    def test_removes_space_com_newsletter(self):
        html = "<p>Content.</p><p>Breaking space news, the latest updates on rocket launches!</p>"
        result = strip_junk(html)
        assert "Breaking space news" not in result

    def test_removes_newsletter_success(self):
        html = "<p>Content.</p><p>You are now subscribed</p><p>Your newsletter sign-up was successful</p>"
        result = strip_junk(html)
        assert "You are now subscribed" not in result
        assert "sign-up was successful" not in result

    def test_removes_sciencedaily_inline_labels(self):
        html = "<p>Content.</p><p>Story Source:</p><p>Cite This Page:</p>"
        result = strip_junk(html)
        assert "Story Source:" not in result
        assert "Cite This Page:" not in result

    def test_removes_fox_news_download_app_cta(self):
        html = "<p>Article text.</p><p>CLICK HERE TO DOWNLOAD THE FOX NEWS APP</p>"
        result = strip_junk(html)
        assert "CLICK HERE" not in result
        assert "Article text" in result

    def test_removes_fox_news_click_for_more(self):
        html = "<p>Content.</p><p>CLICK HERE FOR MORE SPORTS COVERAGE ON FOXNEWS.COM</p>"
        result = strip_junk(html)
        assert "CLICK HERE FOR MORE" not in result

    def test_removes_fox_news_sign_up_cta(self):
        html = "<p>Content.</p><p>CLICK HERE TO SIGN UP FOR OUR LIFESTYLE NEWSLETTER</p>"
        result = strip_junk(html)
        assert "CLICK HERE TO SIGN UP" not in result

    def test_removes_fox_news_like_reading_cta(self):
        html = "<p>Content.</p><p>LIKE WHAT YOU'RE READING? CLICK HERE FOR MORE ENTERTAINMENT NEWS</p>"
        result = strip_junk(html)
        assert "LIKE WHAT YOU" not in result

    def test_removes_fox_news_follow_cta(self):
        html = "<p>Content.</p><p>Follow Fox News Digital's sports coverage on X and subscribe to the Fox News Sports Huddle newsletter.</p>"
        result = strip_junk(html)
        assert "Follow Fox News" not in result

    def test_preserves_click_here_in_context(self):
        html = "<p>Click here to see the full report on the government website.</p>"
        result = strip_junk(html)
        assert "Click here to see" in result


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
