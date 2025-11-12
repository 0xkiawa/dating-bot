"""
SQLAlchemy migration script to add 'hosting' column to profiles table.
Run this once before deploying the new code.

Usage: python migrate_add_hosting.py
"""

import asyncio
from sqlalchemy import text
from database.connect import async_engine


async def add_hosting_column():
    """Add hosting column to profiles table using SQLAlchemy"""
    
    print("=" * 60)
    print("DATABASE MIGRATION: Adding 'hosting' column")
    print("=" * 60)
    print()
    
    try:
        async with async_engine.begin() as conn:
            # Check if column already exists
            print("Checking if 'hosting' column exists...")
            
            # For SQLite
            result = await conn.execute(text("PRAGMA table_info(profiles)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'hosting' in columns:
                print("✅ 'hosting' column already exists!")
                print()
                return True
            
            # Add hosting column
            print("Adding 'hosting' column to profiles table...")
            await conn.execute(text("""
                ALTER TABLE profiles 
                ADD COLUMN hosting VARCHAR(20)
            """))
            
            print("✅ Successfully added 'hosting' column!")
            print()
            print("ℹ️  Column details:")
            print("   - Type: VARCHAR(20)")
            print("   - Nullable: Yes")
            print("   - Valid values: 'yes', 'no', 'airbnb'")
            print()
            print("ℹ️  Existing profiles will have NULL hosting value")
            print("ℹ️  Users will need to update their profiles to set hosting preference")
            print()
            return True
            
    except Exception as e:
        print(f"❌ Migration error: {e}")
        print()
        return False


async def main():
    success = await add_hosting_column()
    
    if success:
        print("=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Deploy the updated code")
        print("2. Existing users will see NULL hosting - they can recreate profiles")
        print("3. New users will be asked hosting during profile creation")
        print()
    else:
        print("=" * 60)
        print("❌ Migration failed!")
        print("=" * 60)
        print("Please check the errors above and try again.")
        print()
    
    # Close the engine
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())