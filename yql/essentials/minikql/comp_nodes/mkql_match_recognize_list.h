#pragma once

#include "mkql_match_recognize_save_load.h"
#include "mkql_match_recognize_version.h"

#include <yql/essentials/minikql/defs.h>
#include <yql/essentials/minikql/computation/mkql_computation_node_impl.h>
#include <yql/essentials/minikql/computation/mkql_computation_node_holders.h>
#include <yql/essentials/minikql/comp_nodes/mkql_saveload.h>
#include <yql/essentials/public/udf/udf_value.h>
#include <unordered_map>

namespace NKikimr::NMiniKQL::NMatchRecognize {

class TSimpleList {
public:
    ///Range that includes starting and ending points
    ///Can not be empty
    class TRange {
    public:
        TRange()
        : FromIndex(Max())
        , ToIndex(Max())
        , NfaIndex_(Max())
        {
        }

        explicit TRange(ui64 index)
            : FromIndex(index)
            , ToIndex(index)
            , NfaIndex_(Max())
        {
        }

        TRange(ui64 from, ui64 to)
            : FromIndex(from)
            , ToIndex(to)
            , NfaIndex_(Max())
        {
            MKQL_ENSURE(FromIndex <= ToIndex, "Internal logic error");
        }

        bool IsValid() const {
            return FromIndex != Max<size_t>() && ToIndex != Max<size_t>();
        }

        size_t From() const {
            MKQL_ENSURE(IsValid(), "Internal logic error");
            return FromIndex;
        }

        size_t To() const {
            MKQL_ENSURE(IsValid(), "Internal logic error");
            return ToIndex;
        }

        [[nodiscard]] size_t NfaIndex() const {
            MKQL_ENSURE(IsValid(), "Internal logic error");
            return NfaIndex_;
        }

        size_t Size() const {
            MKQL_ENSURE(IsValid(), "Internal logic error");
            return ToIndex - FromIndex + 1;
        }

        void Extend() {
            MKQL_ENSURE(IsValid(), "Internal logic error");
            ++ToIndex;
        }

    private:
        size_t FromIndex;
        size_t ToIndex;
        size_t NfaIndex_;
    };

    TRange Append(NUdf::TUnboxedValue&& value) {
        TRange result(Rows.size());
        Rows.push_back(std::move(value));
        return result;
    }

    size_t Size() const {
        return Rows.size();
    }

    bool Empty() const {
        return Size() == 0;
    }

    NUdf::TUnboxedValue Get(size_t i) const {
        return Rows.at(i);
    }
private:
    TUnboxedValueVector Rows;
};

///Stores only locked items
///Locks are holds by TRange
///When all locks on an item are released, the item is removed from the list
class TSparseList {
    struct TItem {
        NUdf::TUnboxedValue Value;
        size_t LockCount = 0;
    };

    class TContainer: public TSimpleRefCount<TContainer> {
    public:
        using TPtr = TIntrusivePtr<TContainer>;

        void Add(size_t index, NUdf::TUnboxedValue&& value) {
            const auto& [iter, newOne] = Storage.emplace(index, TItem{std::move(value), 1});
            MKQL_ENSURE(newOne, "Internal logic error");
        }

        size_t Size() const {
            return Storage.size();
        }

        NUdf::TUnboxedValue Get(size_t i) const {
            if (const auto it = Storage.find(i); it != Storage.cend()) {
                return it->second.Value;
            } else {
                return NUdf::TUnboxedValue{};
            }
        }

        void LockRange(size_t from, size_t to) {
            for (auto i = from; i <= to; ++i) {
                const auto it = Storage.find(i);
                MKQL_ENSURE(it != Storage.cend(), "Internal logic error");
                ++it->second.LockCount;
            }
        }

        void UnlockRange(size_t from, size_t to) {
            for (auto i = from; i <= to; ++i) {
                const auto it = Storage.find(i);
                MKQL_ENSURE(it != Storage.cend(), "Internal logic error");
                auto lockCount = --it->second.LockCount;
                if (0 == lockCount) {
                    Storage.erase(it);
                }
            }
        }

        void Save(TMrOutputSerializer& serializer) const {
            serializer(Storage.size());
            for (const auto& [key, item]: Storage) {
                serializer(key, item.Value, item.LockCount);
            }
        }

        void Load(TMrInputSerializer& serializer) {
            auto size = serializer.Read<TStorage::size_type>();
            Storage.reserve(size);
            for (size_t i = 0; i < size; ++i) {
                TStorage::key_type key;
                NUdf::TUnboxedValue row;
                decltype(TItem::LockCount) lockCount;
                serializer(key, row, lockCount);
                Storage.emplace(key, TItem{row, lockCount});
            }
        }

    private:
        //TODO consider to replace hash table with contiguous chunks
        using TStorage = std::unordered_map<
            size_t,
            TItem,
            std::hash<size_t>,
            std::equal_to<size_t>,
            TMKQLAllocator<std::pair<const size_t, TItem>, EMemorySubPool::Temporary>>;

        TStorage Storage;
    };
    using TContainerPtr = TContainer::TPtr;

public:
    ///Range that includes starting and ending points
    ///Holds a lock on items in the list
    ///Can not be empty, but can be in invalid state, with no container set
    class TRange{
        friend class TSparseList;
    public:
        TRange()
            : Container()
            , FromIndex(Max())
            , ToIndex(Max())
            , NfaIndex_(Max())
        {
        }

        TRange(const TRange& other)
            : Container(other.Container)
            , FromIndex(other.FromIndex)
            , ToIndex(other.ToIndex)
            , NfaIndex_(other.NfaIndex_)
        {
            LockRange(FromIndex, ToIndex);
        }

        TRange(TRange&& other)
            : Container(other.Container)
            , FromIndex(other.FromIndex)
            , ToIndex(other.ToIndex)
            , NfaIndex_(other.NfaIndex_)
        {
            other.Reset();
        }

        ~TRange() {
            Release();
        }

        TRange& operator=(const TRange& other) {
            if (&other == this) {
                return *this;
            }
            //TODO(zverevgeny): optimize for overlapped source and destination
            Release();
            Container = other.Container;
            FromIndex = other.FromIndex;
            ToIndex = other.ToIndex;
            NfaIndex_ = other.NfaIndex_;
            LockRange(FromIndex, ToIndex);
            return *this;
        }

        TRange& operator=(TRange&& other) {
            if (&other == this) {
                return *this;
            }
            Release();
            Container = other.Container;
            FromIndex = other.FromIndex;
            ToIndex = other.ToIndex;
            NfaIndex_ = other.NfaIndex_;
            other.Reset();
            return *this;
        }

        friend inline bool operator==(const TRange& lhs, const TRange& rhs) {
            return std::tie(lhs.FromIndex, lhs.ToIndex, lhs.NfaIndex_) == std::tie(rhs.FromIndex, rhs.ToIndex, rhs.NfaIndex_);
        }

        friend inline bool operator<(const TRange& lhs, const TRange& rhs) {
            return std::tie(lhs.FromIndex, lhs.ToIndex, lhs.NfaIndex_) < std::tie(rhs.FromIndex, rhs.ToIndex, rhs.NfaIndex_);
        }

        bool IsValid() const {
            return static_cast<bool>(Container) && FromIndex != Max<size_t>() && ToIndex != Max<size_t>();
        }

        size_t From() const {
            MKQL_ENSURE(IsValid(), "Internal logic error");
            return FromIndex;
        }

        size_t To() const {
            MKQL_ENSURE(IsValid(), "Internal logic error");
            return ToIndex;
        }

        [[nodiscard]] size_t NfaIndex() const {
            MKQL_ENSURE(IsValid(), "Internal logic error");
            return NfaIndex_;
        }

        void NfaIndex(size_t index) {
            NfaIndex_ = index;
        }

        size_t Size() const {
            MKQL_ENSURE(IsValid(), "Internal logic error");
            return ToIndex - FromIndex + 1;
        }

        void Extend() {
            MKQL_ENSURE(IsValid(), "Internal logic error");
            ++ToIndex;
            LockRange(ToIndex, ToIndex);
        }

        void Release() {
            UnlockRange(FromIndex, ToIndex);
            Container.Reset();
            FromIndex = Max();
            ToIndex = Max();
            NfaIndex_ = Max();
        }

        void Save(TMrOutputSerializer& serializer) const {
            serializer(Container, FromIndex, ToIndex, NfaIndex_);
       }

        void Load(TMrInputSerializer& serializer) {
            serializer(Container, FromIndex, ToIndex);
            if (serializer.GetStateVersion() >= 2U) {
                serializer(NfaIndex_);
            }
        }

    private:
        TRange(TContainerPtr container, size_t index)
            : Container(container)
            , FromIndex(index)
            , ToIndex(index)
            , NfaIndex_(Max())
        {}

        void LockRange(size_t from, size_t to) {
            if (Container) {
                Container->LockRange(from, to);
            }
        }

        void UnlockRange(size_t from, size_t to) {
            if (Container) {
                Container->UnlockRange(from, to);
            }
        }

        void Reset() {
            Container.Reset();
            FromIndex = Max();
            ToIndex = Max();
            NfaIndex_ = Max();
        }

        TContainerPtr Container;
        size_t FromIndex;
        size_t ToIndex;
        size_t NfaIndex_;
    };

public:
    TRange Append(NUdf::TUnboxedValue&& value) {
        const auto index = ListSize++;
        Container->Add(index, std::move(value));
        return TRange(Container, index);
    }

    NUdf::TUnboxedValue Get(size_t i) const {
        return Container->Get(i);
    }

    ///Return total size of sparse list including absent values
    size_t Size() const {
        return ListSize;
    }

    ///Return number of present values in sparse list
    size_t Filled() const {
        return Container->Size();
    }

    bool Empty() const {
        return Size() == 0;
    }

    void Save(TMrOutputSerializer& serializer) const {
        serializer(Container, ListSize);
    }

    void Load(TMrInputSerializer& serializer) {
        serializer(Container, ListSize);
    }

private:
    TContainerPtr Container = MakeIntrusive<TContainer>();
    size_t ListSize = 0; //impl: max index ever stored + 1
};

template<typename L>
class TListValue: public TComputationValue<TListValue<L>> {
public:
    TListValue(TMemoryUsageInfo* memUsage, const L& list)
        : TComputationValue<TListValue<L>>(memUsage)
        , List(list)
    {
    }

    //TODO https://st.yandex-team.ru/YQL-16508
    //NUdf::TUnboxedValue GetListIterator() const override;

    bool HasFastListLength() const override {
        return !List.Empty();
    }

    ui64 GetListLength() const override {
        return List.Size();
    }

    bool HasListItems() const override {
        return !List.Empty();
    }

    NUdf::IBoxedValuePtr ToIndexDictImpl(const NUdf::IValueBuilder& builder) const override {
        Y_UNUSED(builder);
        return const_cast<TListValue*>(this);
    }

    NUdf::TUnboxedValue Lookup(const NUdf::TUnboxedValuePod& key) const override {
        return List.Get(key.Get<ui64>());
    }

private:
    L List;
};

}//namespace NKikimr::NMiniKQL::NMatchRecognize

