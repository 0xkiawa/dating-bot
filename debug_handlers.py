"""
Debug script to find all handlers that might catch "📭" message
Run this from your project root: python debug_handlers.py
"""

import os
import re
from pathlib import Path


def find_message_handlers(directory="app/handlers"):
    """Find all message handlers in the handlers directory"""
    handlers = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py') and file != '__init__.py':
                filepath = os.path.join(root, file)
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Find all @router.message decorators
                    pattern = r'@\w+_router\.message\([^)]*\)'
                    matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
                    
                    for match in matches:
                        decorator = match.group()
                        # Get the function name
                        func_pattern = r'async def (\w+)\('
                        func_match = re.search(func_pattern, content[match.end():match.end()+200])
                        func_name = func_match.group(1) if func_match else "unknown"
                        
                        handlers.append({
                            'file': filepath,
                            'decorator': decorator,
                            'function': func_name,
                            'line': content[:match.start()].count('\n') + 1
                        })
    
    return handlers


def analyze_handlers():
    """Analyze handlers and find potential conflicts"""
    print("=" * 80)
    print("HANDLER ANALYSIS - Looking for handlers that might catch '📭'")
    print("=" * 80)
    print()
    
    handlers = find_message_handlers()
    
    # Check for handlers that might catch 📭
    print("📋 ALL MESSAGE HANDLERS:\n")
    
    catch_all = []
    specific = []
    
    for h in handlers:
        decorator = h['decorator']
        
        # Check if it's a catch-all handler
        is_catch_all = (
            'F.text' in decorator and 
            '==' not in decorator and 
            '.in_' not in decorator
        ) or (
            '@' in decorator and 
            'message' in decorator and
            '()' in decorator  # Empty filter
        )
        
        # Check if it specifically handles 📭
        handles_mailbox = '📭' in decorator or '"📭"' in decorator or "'📭'" in decorator
        
        info = f"  File: {h['file']}:{h['line']}\n  Function: {h['function']}\n  Filter: {decorator}\n"
        
        if handles_mailbox:
            print(f"✅ HANDLES 📭:\n{info}")
            specific.append(h)
        elif is_catch_all:
            print(f"⚠️  CATCH-ALL (might intercept 📭):\n{info}")
            catch_all.append(h)
    
    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY:")
    print("=" * 80)
    print(f"\n✅ Handlers specifically for 📭: {len(specific)}")
    for h in specific:
        print(f"   - {h['file']} (line {h['line']})")
    
    print(f"\n⚠️  Catch-all handlers that might intercept: {len(catch_all)}")
    for h in catch_all:
        print(f"   - {h['file']} (line {h['line']}) - {h['function']}")
    
    print("\n" + "=" * 80)
    print("ROUTER REGISTRATION ORDER:")
    print("=" * 80)
    
    # Check router registration order
    init_file = "app/handlers/__init__.py"
    if os.path.exists(init_file):
        with open(init_file, 'r') as f:
            content = f.read()
            
        # Find include_routers line
        router_match = re.search(r'include_routers?\((.*?)\)', content, re.DOTALL)
        if router_match:
            routers = router_match.group(1)
            print(f"\nRouters are registered in this order:")
            for router in re.findall(r'(\w+_router)', routers):
                print(f"  {router}")
            
            print(f"\n💡 TIP: Routers run in order. If common_router comes before dating_router,")
            print(f"   its handlers will run first and might catch messages before dating_router.")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS:")
    print("=" * 80)
    
    if catch_all:
        print("\n⚠️  Found catch-all handlers that might be intercepting '📭':")
        print("   Solution 1: Make catch-all handlers more specific")
        print("   Solution 2: Move dating_router BEFORE common_router in include_routers()")
        print("   Solution 3: Add StateFilter to catch-all handlers")
    
    if not specific:
        print("\n❌ No handler found for '📭' emoji!")
        print("   Make sure inbox.py is imported in app/handlers/dating/__init__.py")
    elif len(specific) > 1:
        print(f"\n⚠️  Multiple handlers found for '📭'! Only the first one will run.")
        print("   Check for duplicate handlers.")
    else:
        print("\n✅ Found exactly one handler for '📭'")
        if catch_all:
            print("   But catch-all handlers might be intercepting it first!")


if __name__ == "__main__":
    try:
        analyze_handlers()
        print("\n✅ Analysis complete!\n")
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()