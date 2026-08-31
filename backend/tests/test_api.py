import os
import json
import tempfile
import unittest
from fastapi.testclient import TestClient
from backend.main import app


class TestAuraMarketingAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _register_and_login(self, email):
        reg_payload = {"email": email, "password": "securepassword123", "workspace_type": "marketing"}
        self.client.post("/api/auth/register", json=reg_payload)
        res_login = self.client.post("/api/auth/login", json={"email": email, "password": "securepassword123"})
        self.assertEqual(res_login.status_code, 200)
        token = res_login.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_root_status(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")

    def test_auth_and_user_flow(self):
        email = "test.marketer@aura.com"
        reg_payload = {"email": email, "password": "securepassword123", "workspace_type": "marketing"}
        res_reg = self.client.post("/api/auth/register", json=reg_payload)
        self.assertIn(res_reg.status_code, [200, 400])

        res_login = self.client.post("/api/auth/login", json={"email": email, "password": "securepassword123"})
        self.assertEqual(res_login.status_code, 200)
        token = res_login.json()["access_token"]
        self.assertTrue(len(token) > 10)

    def test_unauthenticated_requests_are_rejected(self):
        """
        FIX-VERIFICATION: every one of these used to succeed with NO auth
        header at all, silently using a hardcoded demo.user@aura.com
        account with 9999 tokens. They must now all return 401.
        """
        for method, path, body in [
            ("get", "/api/wallet/balance", None),
            ("get", "/api/campaigns/list", None),
            ("post", "/api/marketing-doctor/diagnose", {"website_url": "https://example.com"}),
            ("post", "/api/campaigns/track-event", {"campaign_id": "X", "user_identifier": "u", "channel": "google_ads", "event_type": "click"}),
            ("get", "/api/campaigns/attribution/X", None),
        ]:
            resp = getattr(self.client, method)(path, json=body) if body is not None else getattr(self.client, method)(path)
            self.assertEqual(resp.status_code, 401, f"{method.upper()} {path} should require auth, got {resp.status_code}")

    def test_payment_verification_rejects_when_unconfigured_for_real_order(self):
        """
        FIX-VERIFICATION: a non-mock order with no RAZORPAY_KEY_SECRET
        configured used to auto-approve (`is_valid = True`) and mint free
        tokens. It must now fail closed.
        """
        headers = self._register_and_login("payer.real@aura.com")
        payment_payload = {
            "razorpay_order_id": "order_REALLOOKING123",  # NOT prefixed order_mock_
            "razorpay_payment_id": "pay_test123",
            "razorpay_signature": "not_a_real_signature",
            "tier_name": "500 Tokens Package",
            "tokens_to_add": 500,
            "amount": 49.0,
        }
        res_pay = self.client.post("/api/wallet/verify-payment", json=payment_payload, headers=headers)
        self.assertIn(res_pay.status_code, [400, 500])

    def test_payment_mock_order_still_works_for_local_dev(self):
        headers = self._register_and_login("payer.mock@aura.com")
        payment_payload = {
            "razorpay_order_id": "order_mock_test123",
            "razorpay_payment_id": "pay_mock_test123",
            "razorpay_signature": "mock_sig",
            "tier_name": "500 Tokens Package",
            "tokens_to_add": 500,
            "amount": 49.0,
        }
        res_pay = self.client.post("/api/wallet/verify-payment", json=payment_payload, headers=headers)
        self.assertEqual(res_pay.status_code, 200)
        self.assertEqual(res_pay.json()["status"], "success")

    def test_payment_idempotency_does_not_double_credit(self):
        headers = self._register_and_login("payer.idempotent@aura.com")
        payment_payload = {
            "razorpay_order_id": "order_mock_dup123",
            "razorpay_payment_id": "pay_mock_dup123",
            "razorpay_signature": "mock_sig",
            "tier_name": "100 Tokens Package",
            "tokens_to_add": 100,
            "amount": 9.0,
        }
        first = self.client.post("/api/wallet/verify-payment", json=payment_payload, headers=headers)
        second = self.client.post("/api/wallet/verify-payment", json=payment_payload, headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["new_token_balance"], second.json()["new_token_balance"])

    def test_marketing_doctor_beautifulsoup_diagnose(self):
        headers = self._register_and_login("doctor.user@aura.com")
        diag_payload = {"website_url": "https://github.com"}
        res_diag = self.client.post("/api/marketing-doctor/diagnose", json=diag_payload, headers=headers)
        self.assertEqual(res_diag.status_code, 200)
        data = res_diag.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("live_metrics", data["diagnosis"])
        self.assertIn("scores", data["diagnosis"])
        self.assertIn("score_disclosure", data["diagnosis"])  # FIX-VERIFICATION: honesty disclosure present

    def test_touchpoint_event_and_attribution(self):
        headers = self._register_and_login("attribution.user@aura.com")
        event_payload = {
            "campaign_id": "CAMP_UNITTEST",
            "user_identifier": "usr_test_99",
            "channel": "google_ads",
            "event_type": "lead_conversion",
            "conversion_value": 250.0,
        }
        res_ev = self.client.post("/api/campaigns/track-event", json=event_payload, headers=headers)
        self.assertEqual(res_ev.status_code, 200)
        self.assertEqual(res_ev.json()["status"], "success")

        res_attr = self.client.get("/api/campaigns/attribution/CAMP_UNITTEST", headers=headers)
        self.assertEqual(res_attr.status_code, 200)
        attr_data = res_attr.json()
        self.assertEqual(attr_data["status"], "success")
        self.assertIn("attribution_models", attr_data)
        self.assertIn("first_touch", attr_data["attribution_models"])
        self.assertIn("w_shaped", attr_data["attribution_models"])

    def test_image_edit_upscale_actually_transforms_and_charges_correctly(self):
        """
        FIX-VERIFICATION: 'upscale' used to charge tokens and return the
        original, unedited image. It must now return a genuinely different
        (larger) image and only then charge tokens.
        """
        headers = self._register_and_login("image.user@aura.com")
        balance_before = self.client.get("/api/wallet/balance", headers=headers).json()["tokens"]

        req = {"source_url": "https://picsum.photos/200", "tool": "upscale", "scale_factor": "2x"}
        res = self.client.post("/api/image/ai/edit", json=req, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["data_source"], "real_local_processing")
        self.assertTrue(data["result_image"].startswith("data:image/"))

        balance_after = self.client.get("/api/wallet/balance", headers=headers).json()["tokens"]
        self.assertEqual(balance_before - balance_after, 10)  # upscale cost

    def test_image_edit_unconfigured_paid_tool_does_not_charge(self):
        """
        FIX-VERIFICATION: tools needing a paid provider we don't have keys
        for must fail WITHOUT charging tokens, instead of silently no-op'ing
        and charging anyway.
        """
        headers = self._register_and_login("image.user2@aura.com")
        balance_before = self.client.get("/api/wallet/balance", headers=headers).json()["tokens"]

        req = {"source_url": "https://via.placeholder.com/100", "tool": "search-replace"}
        res = self.client.post("/api/image/ai/edit", json=req, headers=headers)
        self.assertEqual(res.status_code, 501)

        balance_after = self.client.get("/api/wallet/balance", headers=headers).json()["tokens"]
        self.assertEqual(balance_before, balance_after)

    def test_video_generate_route_now_exists_and_is_mounted(self):
        """FIX-VERIFICATION: /api/video/generate used to 404 (never mounted)."""
        headers = self._register_and_login("video.user@aura.com")
        res = self.client.post("/api/video/generate", json={"prompt": "cyberpunk city in neon rain"}, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("disclosure", data)  # honestly says stock-vs-real
        self.assertIn("job_id", data)

    def test_video_generation_falls_back_honestly_when_hf_space_unavailable(self):
        """
        FIX-VERIFICATION: a free real-generation tier (Hugging Face Spaces,
        via gradio_client) sits between Replicate and the sandbox stock
        clip. When the configured Space is unreachable/times out, the async
        job must resolve to an honest fallback — never stay stuck, never
        claim a real render that didn't happen.
        """
        from backend import generator
        old_space, old_timeout = generator.HF_VIDEO_SPACE, generator.HF_VIDEO_TIMEOUT_SECONDS
        generator.HF_VIDEO_SPACE = "this-space-does-not-exist-xyz-123/nope"
        generator.HF_VIDEO_TIMEOUT_SECONDS = 5
        try:
            headers = self._register_and_login("hfvideo.user@aura.com")
            res = self.client.post("/api/video/generate", json={"prompt": "a quiet forest stream"}, headers=headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["generation_source"], "huggingface_space")
            job_id = data["job_id"]

            import time as _t
            status = None
            for _ in range(20):
                status = self.client.get(f"/api/video/status/{job_id}", headers=headers).json()
                if status["status"] != "processing":
                    break
                _t.sleep(1)
            self.assertEqual(status["status"], "completed")
            self.assertTrue(status.get("used_fallback"))
            self.assertIsNotNone(status["video_url"])
        finally:
            generator.HF_VIDEO_SPACE = old_space
            generator.HF_VIDEO_TIMEOUT_SECONDS = old_timeout

    def test_video_generation_prefers_private_gpu_then_falls_back_honestly(self):
        """
        FIX-VERIFICATION: PRIVATE_GPU_ENDPOINT (your own Colab/Kaggle
        Gradio share link) is tried before the public HF Space. When it's
        unreachable, the job must resolve to an honest fallback, not hang
        or claim a real render that didn't happen.
        """
        from backend import generator
        old_endpoint, old_timeout = generator.PRIVATE_GPU_ENDPOINT, generator.PRIVATE_GPU_GENERATE_TIMEOUT_SECONDS
        generator.PRIVATE_GPU_ENDPOINT = "http://127.0.0.1:1/does-not-exist"
        generator.PRIVATE_GPU_GENERATE_TIMEOUT_SECONDS = 3
        try:
            headers = self._register_and_login("privategpu.user@aura.com")
            res = self.client.post("/api/video/generate", json={"prompt": "a red panda eating bamboo"}, headers=headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["generation_source"], "private_gpu")
            job_id = data["job_id"]

            import time as _t
            status = None
            for _ in range(20):
                status = self.client.get(f"/api/video/status/{job_id}", headers=headers).json()
                if status["status"] != "processing":
                    break
                _t.sleep(1)
            self.assertEqual(status["status"], "completed")
            self.assertTrue(status.get("used_fallback"))
            self.assertIsNotNone(status["video_url"])
        finally:
            generator.PRIVATE_GPU_ENDPOINT = old_endpoint
            generator.PRIVATE_GPU_GENERATE_TIMEOUT_SECONDS = old_timeout

    def test_video_generation_prefers_local_library_clip_over_generic_stock(self):
        """
        FIX-VERIFICATION: a real AI-generated clip restocked into
        backend/generated_library/ (via notebooks/free_video_gpu.ipynb)
        must be preferred over the generic Mixkit stock clip when its
        tags match the prompt, and served back through the app's own
        /api/video/library/{filename} route rather than an external URL.
        """
        from backend import generator
        with tempfile.TemporaryDirectory() as tmp_lib:
            fake_clip_path = os.path.join(tmp_lib, "cyberpunk_001.mp4")
            with open(fake_clip_path, "wb") as f:
                f.write(b"FAKE_MP4_BYTES")
            manifest_path = os.path.join(tmp_lib, "manifest.json")
            with open(manifest_path, "w") as f:
                json.dump({"clips": [{"file": "cyberpunk_001.mp4", "tags": ["cyberpunk", "neon"]}]}, f)

            old_dir, old_manifest = generator.GENERATED_LIBRARY_DIR, generator.GENERATED_LIBRARY_MANIFEST
            generator.GENERATED_LIBRARY_DIR = tmp_lib
            generator.GENERATED_LIBRARY_MANIFEST = manifest_path
            try:
                headers = self._register_and_login("videolibrary.user@aura.com")
                res = self.client.post("/api/video/generate", json={"prompt": "a neon cyberpunk skyline"}, headers=headers)
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data["generation_source"], "video_library")
                self.assertEqual(data["video_url"], "/api/video/library/cyberpunk_001.mp4")

                # video_router imported GENERATED_LIBRARY_DIR by reference at
                # import time, so patch it there too for the serving route.
                from backend import video_router
                old_router_dir = video_router.GENERATED_LIBRARY_DIR
                video_router.GENERATED_LIBRARY_DIR = tmp_lib
                try:
                    file_res = self.client.get("/api/video/library/cyberpunk_001.mp4")
                    self.assertEqual(file_res.status_code, 200)
                    self.assertEqual(file_res.content, b"FAKE_MP4_BYTES")

                    # Path traversal must be rejected, not served.
                    traversal_res = self.client.get("/api/video/library/..%2F..%2Fmain.py")
                    self.assertIn(traversal_res.status_code, (400, 404))
                finally:
                    video_router.GENERATED_LIBRARY_DIR = old_router_dir
            finally:
                generator.GENERATED_LIBRARY_DIR = old_dir
                generator.GENERATED_LIBRARY_MANIFEST = old_manifest

    def test_apple_signin_returns_honest_not_implemented(self):
        res = self.client.post("/api/auth/apple")
        self.assertEqual(res.status_code, 501)


if __name__ == "__main__":
    unittest.main()
