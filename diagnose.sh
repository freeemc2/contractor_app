#!/bin/bash
echo "=== FLASK APP DIAGNOSTICS ==="
echo ""

echo "1. Checking if Flask is running..."
ps aux | grep "python3 app.py" | grep -v grep
if [ $? -eq 0 ]; then
    echo "✅ Flask process found"
else
    echo "❌ Flask NOT running!"
fi
echo ""

echo "2. Checking Flask health endpoint..."
curl -s http://82.25.74.217:5003/health 2>&1
echo ""
echo ""

echo "3. Checking database..."
sqlite3 instance/contractor_leads.db "SELECT COUNT(*) as total_leads FROM leads;" 2>&1
echo ""

echo "4. Checking recent Flask logs (last 30 lines)..."
tail -30 /tmp/contractor_app.log 2>&1
echo ""

echo "5. Checking if port 5003 is listening..."
netstat -tlnp | grep 5003
echo ""

echo "6. Testing login page..."
curl -s http://82.25.74.217:5003/login 2>&1 | head -10
echo ""

echo "=== END DIAGNOSTICS ==="
