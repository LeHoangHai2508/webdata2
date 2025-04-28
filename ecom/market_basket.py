from collections import defaultdict
from itertools import combinations

#Implement the Apriori algorithm for finding frequent itemsets
class MarketBasketAnalysis:
    def __init__(self, min_support=0.1, min_confidence=0.5):
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.frequent_itemsets = []
        self.association_rules = []

    def get_transactions(self):
        from .models import Transaction
        transactions = []
        current_order = None
        current_items = set()
        
        for t in Transaction.objects.all().order_by('order', 'product'):
            if current_order != t.order:
                if current_items:
                    transactions.append(current_items)
                current_order = t.order
                current_items = set()
            current_items.add(t.product.id)
        
        if current_items:
            transactions.append(current_items)
            
        return transactions

    def get_support(self, itemset, transactions):
        count = 0
        for transaction in transactions:
            if itemset.issubset(transaction):
                count += 1
        return count / len(transactions)

    def get_frequent_itemsets(self, transactions):
        items = set()
        for transaction in transactions:
            for item in transaction:
                items.add(frozenset([item]))
        
        self.frequent_itemsets = []
        k = 1
        
        while items:
            # Calculate support for current itemsets
            current_frequent = []
            for itemset in items:
                support = self.get_support(itemset, transactions)
                if support >= self.min_support:
                    current_frequent.append((itemset, support))
            
            if not current_frequent:
                break
                
            self.frequent_itemsets.extend(current_frequent)
            
            # Generate next level itemsets
            items = set()
            for i in range(len(current_frequent)):
                for j in range(i + 1, len(current_frequent)):
                    new_itemset = current_frequent[i][0].union(current_frequent[j][0])
                    if len(new_itemset) == k + 1:
                        items.add(new_itemset)
            
            k += 1

    def generate_rules(self):
        self.association_rules = []
        for itemset, support in self.frequent_itemsets:
            if len(itemset) < 2:
                continue
                
            for i in range(1, len(itemset)):
                for antecedent in combinations(itemset, i):
                    antecedent = frozenset(antecedent)
                    consequent = itemset - antecedent
                    
                    # Find support of antecedent
                    antecedent_support = next(s for s, sup in self.frequent_itemsets if s == antecedent)[1]
                    
                    confidence = support / antecedent_support
                    if confidence >= self.min_confidence:
                        self.association_rules.append({
                            'antecedent': antecedent,
                            'consequent': consequent,
                            'support': support,
                            'confidence': confidence
                        })

    def analyze(self):
        transactions = self.get_transactions()
        self.get_frequent_itemsets(transactions)
        self.generate_rules()
        return self.association_rules 