#include <iostream>
using namespace std;

class Base{
   public:
   int x;
      Base() {cout << "Base Constructed" << endl;}
      ~Base() {cout << "Base Destructed" << endl;}
};

class Base1: public Base{
   public:
};
// class Base2: public Base{
//    public:
//       Base2() {cout << "Base2 Constructed" << endl;}
//       ~Base2() {cout << "Base2 Destructed" << endl;}
// };
// class Derived: public Base2, public Base1{
//    public:
//       Derived() {
//          cout << "Derived Constructed" << endl;
//       }
//       ~Derived() {
//          cout << "Derived Destructed" << endl;
//       }
// };

int main() {   
   Base1 d;
   d.x = 1;
   cout << d.x << endl;
}


